# backend/routers/purchase_orders.py

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload # <-- import selectinload
from typing import List, Optional
import logging
from datetime import date, datetime
from decimal import Decimal
import os
import uuid
from utils.auth_utils import get_current_user, get_user_identifier
from utils.tenancy import get_tenant_id
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict
import pytz
from pydantic import BaseModel

try:
    from utils.s3_utils import generate_presigned_upload_url, generate_presigned_download_url
except ImportError:
    generate_presigned_upload_url = None
    generate_presigned_download_url = None

from schemas.purchase_order_items import PurchaseOrderItemUpdate

from database import get_db
from models.purchase_orders import PurchaseOrder as PurchaseOrderModel, PurchaseOrderStatus
from models.purchase_order_items import PurchaseOrderItem as PurchaseOrderItemModel
from models.inventory_items import InventoryItem as InventoryItemModel
from models.inventory_item_audit import InventoryItemAudit
from models.business_partners import BusinessPartner as BusinessPartnerModel
from schemas.purchase_orders import (
    PurchaseOrder as PurchaseOrderSchema,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderItemCreateRequest,
)

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])
logger = logging.getLogger("purchase_orders")

# ... (other endpoints like create_purchase_order, get_purchase_orders, etc.)

@router.get("/{po_id}", response_model=PurchaseOrderSchema)
def get_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Retrieve a single purchase order by ID, with all related details."""
    db_po = (
        db.query(PurchaseOrderModel)
        .filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id)
        .options(
            # Eagerly load the vendor relationship
            selectinload(PurchaseOrderModel.vendor),
            # Eagerly load the items relationship
            selectinload(PurchaseOrderModel.items)
                # And for each item, eagerly load its related inventory_item
                .selectinload(PurchaseOrderItemModel.inventory_item),
            # Also load the payments to display them on the details page
            selectinload(PurchaseOrderModel.payments)
        )
        .first()
    )
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    return db_po
@router.post("/", response_model=PurchaseOrderSchema, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    po: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Create a new purchase order with associated items."""
    # 1. Validate Business Partner (Vendor)
    db_vendor = db.query(BusinessPartnerModel).filter(
        BusinessPartnerModel.id == po.vendor_id, 
        BusinessPartnerModel.tenant_id == tenant_id,
        BusinessPartnerModel.status == 'ACTIVE',
        BusinessPartnerModel.is_vendor
    ).first()
    if not db_vendor:
        raise HTTPException(status_code=400, detail="Business partner not found, inactive, or not a vendor.")

    total_amount = Decimal(0)
    db_po_items = []

    # 3. Prepare Purchase Order Items and calculate total
    if not po.items:
        raise HTTPException(status_code=400, detail="Purchase order must contain at least one item.")

    for item_data in po.items:
        db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_data.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
        if not db_inventory_item:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_data.inventory_item_id} not found.")
        
        if db_inventory_item.category and db_inventory_item.category.lower() == 'supplies':
            raise HTTPException(status_code=400, detail=f"Item '{db_inventory_item.name}' belongs to the 'Supplies' category and cannot be purchased.")
        
        line_total = item_data.quantity * item_data.price_per_unit
        total_amount += line_total
        
        db_po_items.append(
            PurchaseOrderItemModel(
                inventory_item_id=item_data.inventory_item_id,
                quantity=item_data.quantity,
                price_per_unit=item_data.price_per_unit,
                line_total=line_total,
                tenant_id=tenant_id
            )
        )
    
    # 4. Create the Purchase Order
    last_po_number = db.query(func.max(PurchaseOrderModel.po_number)).filter(PurchaseOrderModel.tenant_id == tenant_id).scalar() or 0
    next_po_number = last_po_number + 1

    db_po = PurchaseOrderModel(
        po_number=next_po_number,
        vendor_id=po.vendor_id,
        order_date=po.order_date,
        status=po.status,
        notes=po.notes,
        total_amount=total_amount,
        created_by=get_user_identifier(user),
        tenant_id=tenant_id,
        bill_no=po.bill_no
    )
    db.add(db_po)
    db.flush() # Flush to get db_po.id before adding items

    for item in db_po_items:
        item.purchase_order_id = db_po.id
        db.add(item)
    # Increase inventory immediately for each purchase order item
    for item in db_po_items:
        inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
        if inv is None:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item.inventory_item_id} not found when updating stock.")
        
        old_stock = inv.current_stock or 0

        # Calculate new average cost
        new_quantity = item.quantity
        purchase_price = item.price_per_unit
        current_avg_cost = inv.average_cost or 0
        
        if purchase_price > 0 and old_stock + new_quantity > 0:
            new_avg_cost = ((old_stock * current_avg_cost) + (new_quantity * purchase_price)) / (old_stock + new_quantity)
            inv.average_cost = new_avg_cost
        
        inv.current_stock = old_stock + new_quantity
        
        # Create audit record
        audit = InventoryItemAudit(
            inventory_item_id=inv.id,
            change_type="purchase",
            change_amount=new_quantity,
            old_quantity=old_stock,
            new_quantity=inv.current_stock,
            changed_by=get_user_identifier(user),
            note=f"Received from PO #{db_po.id}",
            tenant_id=tenant_id
        )
        db.add(audit)
        db.add(inv)
    
    db.commit()
    db.refresh(db_po)
    
    # Refresh with relationships for the response
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).filter(PurchaseOrderModel.id == db_po.id, PurchaseOrderModel.tenant_id == tenant_id).first()

    logger.info(f"Purchase Order (ID: {db_po.id}) created for Vendor ID {db_po.vendor_id} by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_po

@router.get("/", response_model=List[PurchaseOrderSchema])
def read_purchase_orders(
    skip: int = 0,
    limit: int = 100,
    vendor_id: Optional[int] = None,
    status: Optional[PurchaseOrderStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Retrieve a list of purchase orders with various filters."""
    query = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.tenant_id == tenant_id)

    if vendor_id:
        query = query.filter(PurchaseOrderModel.vendor_id == vendor_id)
    if status:
        query = query.filter(PurchaseOrderModel.status == status)
    if start_date:
        query = query.filter(PurchaseOrderModel.order_date >= start_date)
    if end_date:
        query = query.filter(PurchaseOrderModel.order_date <= end_date)

    # Eagerly load items and payments for the response model
    purchase_orders = query.order_by(PurchaseOrderModel.order_date.desc(), PurchaseOrderModel.id.desc()).options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).offset(skip).limit(limit).all()
    
    return purchase_orders

@router.get("/{po_id}", response_model=PurchaseOrderSchema)
def read_purchase_order(po_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """Retrieve a single purchase order by ID."""
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    return db_po

@router.patch("/{po_id}", response_model=PurchaseOrderSchema)
def update_purchase_order(
    po_id: int,
    po_update: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Update an existing purchase order (partial update).
    Note: Item additions/removals are handled via separate endpoints."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    old_values = sqlalchemy_to_dict(db_po)

    # Handle inventory changes when PO is marked as received/paid
    new_status = getattr(po_update, 'status', None)
    # Marking as PAID (received): increase inventory
    if new_status == PurchaseOrderStatus.PAID and db_po.status != PurchaseOrderStatus.PAID:
        for item in db_po.items:
            inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
            if inv is None:
                raise HTTPException(status_code=400, detail=f"Inventory item {item.inventory_item_id} not found")

            # Calculate new average cost
            new_quantity = item.quantity
            purchase_price = item.price_per_unit
            current_stock = inv.current_stock or 0
            current_avg_cost = inv.average_cost or 0

            if current_stock + new_quantity > 0:
                new_avg_cost = ((current_stock * current_avg_cost) + (new_quantity * purchase_price)) / (current_stock + new_quantity)
                inv.average_cost = new_avg_cost

            old_stock = inv.current_stock or 0
            inv.current_stock = (inv.current_stock or 0) + item.quantity
            db.add(inv)

            # Create audit record for inventory increase from PO being marked PAID
            audit = InventoryItemAudit(
                inventory_item_id=inv.id,
                change_type="purchase",
                change_amount=new_quantity,
                old_quantity=old_stock,
                new_quantity=inv.current_stock,
                changed_by=get_user_identifier(user),
                note=f"Marked PAID - Received from PO #{po_id}",
                tenant_id=tenant_id
            )
            db.add(audit)

        logger.info(f"PO (ID: {po_id}) marked as 'Paid/Received'. Inventory increased.")
    # If previously PAID and status is changing away, rollback the inventory increase
    elif db_po.status == PurchaseOrderStatus.PAID and new_status != PurchaseOrderStatus.PAID:
        for item in db_po.items:
            inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
            if inv:
                inv.current_stock = (inv.current_stock or 0) - item.quantity
                db.add(inv)
        logger.info(f"PO (ID: {po_id}) un-marked as 'Paid'. Inventory adjusted.")


    po_data = po_update.model_dump(exclude_unset=True)
    # Prevent direct update of total_amount
    po_data.pop("total_amount", None) 

    for key, value in po_data.items():
        setattr(db_po, key, value)
    
    db_po.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_po.updated_by = get_user_identifier(user)
    
    new_values = sqlalchemy_to_dict(db_po)
    log_entry = AuditLogCreate(
        table_name='purchase_orders',
        record_id=str(po_id),
        changed_by=get_user_identifier(user),
        action='UPDATE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)
    db.commit()
    db.refresh(db_po)
    
    # Refresh with relationships for the response
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    
    logger.info(f"Purchase Order (ID: {po_id}) updated by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_po

@router.delete("/{po_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Delete a purchase order. Only DRAFT or CANCELLED POs can be fully deleted.
    Others should be cancelled (status change)."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    if db_po.status != PurchaseOrderStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Purchase Order status is '{db_po.status.value}'. Only 'Draft' POs can be hard deleted. Consider changing status to 'Draft' if you want to remove."
        )
    
    # If PO has been received (even partially), deleting it would affect inventory.
    # This logic would need to reverse inventory updates or be strictly prevented.
    # For now, we assume this strict check is enough.
    if db_po.status in [PurchaseOrderStatus.PARTIALLY_PAID, PurchaseOrderStatus.PAID]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a purchase order that has been partially or fully received. Change status instead."
        )
    # Restore inventory for items on the deleted PO (undo the earlier increment)
    for item in db_po.items:
        inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
        if inv:
            inv.current_stock = (inv.current_stock or 0) - item.quantity
            db.add(inv)

    old_values = sqlalchemy_to_dict(db_po)
    db_po.deleted_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_po.deleted_by = get_user_identifier(user)
    new_values = sqlalchemy_to_dict(db_po)
    log_entry = AuditLogCreate(
        table_name='purchase_orders',
        record_id=str(po_id),
        changed_by=get_user_identifier(user),
        action='DELETE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)
    db.commit()
    logger.info(f"Purchase Order (ID: {po_id}) soft deleted by user {get_user_identifier(user)} for tenant {tenant_id}")
    return {"message": "Purchase Order deleted successfully"}

# --- Purchase Order Item Endpoints (Nested for managing items within a PO) ---

@router.post("/{po_id}/items", response_model=PurchaseOrderSchema, status_code=status.HTTP_201_CREATED)
def add_item_to_purchase_order(
    po_id: int,
    item_request: PurchaseOrderItemCreateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Add a new item to an existing purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    if db_po.status == PurchaseOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot add items to a purchase order with status '{db_po.status.value}'.")

    db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_request.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
    if not db_inventory_item:
        raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_request.inventory_item_id} not found.")

    if db_inventory_item.category and db_inventory_item.category.lower() == 'supplies':
        raise HTTPException(status_code=400, detail=f"Item '{db_inventory_item.name}' belongs to the 'Supplies' category and cannot be purchased.")

    existing_item = db.query(PurchaseOrderItemModel).filter(
        PurchaseOrderItemModel.purchase_order_id == po_id,
        PurchaseOrderItemModel.inventory_item_id == item_request.inventory_item_id,
        PurchaseOrderItemModel.tenant_id == tenant_id
    ).first()
    if existing_item:
        raise HTTPException(status_code=400, detail="This item already exists in this purchase order. Use the update endpoint to change quantity.")

    line_total = item_request.quantity * item_request.price_per_unit
    db_po_item = PurchaseOrderItemModel(
        purchase_order_id=po_id,
        inventory_item_id=item_request.inventory_item_id,
        quantity=item_request.quantity,
        price_per_unit=item_request.price_per_unit,
        line_total=line_total,
        tenant_id=tenant_id
    )
    db.add(db_po_item)
    
    db_po.total_amount += line_total
    
    # Immediately increase inventory for this PO item
    inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_request.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
    
    # Calculate new average cost
    new_quantity = item_request.quantity
    purchase_price = item_request.price_per_unit
    current_stock = inv.current_stock or 0
    current_avg_cost = inv.average_cost or 0

    if current_stock + new_quantity > 0:
        new_avg_cost = ((current_stock * current_avg_cost) + (new_quantity * purchase_price)) / (current_stock + new_quantity)
        inv.average_cost = new_avg_cost

    old_stock = inv.current_stock or 0
    inv.current_stock = current_stock + new_quantity
    db.add(inv)

    # Create audit record for the inventory increase from adding this PO item
    audit = InventoryItemAudit(
        inventory_item_id=inv.id,
        change_type="purchase",
        change_amount=new_quantity,
        old_quantity=old_stock,
        new_quantity=inv.current_stock,
        changed_by=get_user_identifier(user),
        note=f"Added via PO #{po_id}",
        tenant_id=tenant_id
    )
    db.add(audit)
    
    db_po.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_po.updated_by = get_user_identifier(user)
    
    db.commit()
    db.refresh(db_po)

    # Re-query with relationships for a complete response object
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items).selectinload(PurchaseOrderItemModel.inventory_item),
        selectinload(PurchaseOrderModel.vendor)
    ).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()

    logger.info(f"Item {db_inventory_item.name} added to Purchase Order (ID: {po_id}) by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_po


@router.patch("/{po_id}/items/{item_id}", response_model=PurchaseOrderSchema)
def update_item_in_purchase_order(
    po_id: int,
    item_id: int,
    item_update: PurchaseOrderItemUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Update a specific item in a purchase order.
    - If the inventory_item_id is changed, it's treated as a 'reversal' of the old item
      and an 'add' of the new item to ensure correct stock and cost accounting.
    - If only quantity/price is changed, it adjusts the stock based on the delta.
    """
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items).selectinload(PurchaseOrderItemModel.inventory_item)
    ).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()

    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    item_to_update = next((item for item in db_po.items if item.id == item_id), None)
    if not item_to_update:
        raise HTTPException(status_code=404, detail="Purchase Order Item not found")

    if db_po.status == PurchaseOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot modify items for a purchase order with status '{db_po.status.value}'.")

    update_data = item_update.model_dump(exclude_unset=True)
    new_inventory_item_id = update_data.get("inventory_item_id")
    is_item_change = new_inventory_item_id and new_inventory_item_id != item_to_update.inventory_item_id

    if is_item_change:
        # --- Handle full item change (revert old, add new) ---

        # 1. Revert stock for the OLD item
        old_inv_item = item_to_update.inventory_item
        if old_inv_item:
            old_stock = old_inv_item.current_stock or 0
            old_inv_item.current_stock = old_stock - item_to_update.quantity
            db.add(old_inv_item)
            audit = InventoryItemAudit(
                inventory_item_id=old_inv_item.id, change_type="purchase_reversal",
                change_amount=-item_to_update.quantity, old_quantity=old_stock,
                new_quantity=old_inv_item.current_stock, changed_by=get_user_identifier(user),
                note=f"Item changed on PO #{po_id}", tenant_id=tenant_id
            )
            db.add(audit)

        # 2. Validate and add stock for the NEW item
        new_inv_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == new_inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
        if not new_inv_item:
            raise HTTPException(status_code=400, detail=f"New Inventory Item with ID {new_inventory_item_id} not found.")

        new_quantity = Decimal(update_data.get('quantity', item_to_update.quantity))
        new_price = Decimal(update_data.get('price_per_unit', item_to_update.price_per_unit))

        # Add stock for the new item
        current_stock_new_item = new_inv_item.current_stock or 0
        current_avg_cost = new_inv_item.average_cost or 0
        
        if current_stock_new_item + new_quantity > 0:
            new_avg_cost = ((current_stock_new_item * current_avg_cost) + (new_quantity * new_price)) / (current_stock_new_item + new_quantity)
            new_inv_item.average_cost = new_avg_cost

        new_inv_item.current_stock = current_stock_new_item + new_quantity
        db.add(new_inv_item)
        audit = InventoryItemAudit(
            inventory_item_id=new_inv_item.id, change_type="purchase",
            change_amount=new_quantity, old_quantity=current_stock_new_item,
            new_quantity=new_inv_item.current_stock, changed_by=get_user_identifier(user),
            note=f"Item changed on PO #{po_id}", tenant_id=tenant_id
        )
        db.add(audit)
        
        # 3. Update the PO item in the database
        for key, value in update_data.items():
            setattr(item_to_update, key, value)

    else:
        # --- Handle only quantity/price change ---
        old_qty = item_to_update.quantity
        new_qty = Decimal(update_data.get('quantity', old_qty))
        delta = new_qty - old_qty

        if delta != 0:
            inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_to_update.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
            
            # Adjust average cost only if quantity is increasing
            if delta > 0:
                purchase_price = Decimal(update_data.get('price_per_unit', item_to_update.price_per_unit))
                current_stock = inv.current_stock or 0
                current_avg_cost = inv.average_cost or 0
                if current_stock + delta > 0:
                    new_avg_cost = ((current_stock * current_avg_cost) + (delta * purchase_price)) / (current_stock + delta)
                    inv.average_cost = new_avg_cost

            old_stock = inv.current_stock or 0
            inv.current_stock = old_stock + delta
            db.add(inv)
            
            audit = InventoryItemAudit(
                inventory_item_id=inv.id, change_type="purchase_adjustment",
                change_amount=delta, old_quantity=old_stock,
                new_quantity=inv.current_stock, changed_by=get_user_identifier(user),
                note=f"Quantity updated on PO #{po_id}", tenant_id=tenant_id
            )
            db.add(audit)

        for key, value in update_data.items():
            setattr(item_to_update, key, value)

    # Recalculate totals and commit
    item_to_update.line_total = item_to_update.quantity * item_to_update.price_per_unit
    
    db.flush() # Flush the session to update the item's line_total before summing

    db_po.total_amount = sum(item.line_total for item in db_po.items)
    db_po.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_po.updated_by = get_user_identifier(user)

    db.commit()
    db.refresh(db_po)

    logger.info(f"Purchase Order Item (ID: {item_id}) of Purchase Order (ID: {po_id}) updated by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_po

@router.delete("/{po_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item_from_purchase_order(
    po_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Remove an item from a purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    if db_po.status == PurchaseOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot remove items from a purchase order with status '{db_po.status.value}'.")
        
    db_po_item = db.query(PurchaseOrderItemModel).filter(
        PurchaseOrderItemModel.id == item_id,
        PurchaseOrderItemModel.purchase_order_id == po_id,
        PurchaseOrderItemModel.tenant_id == tenant_id
    ).first()
    if db_po_item is None:
        raise HTTPException(status_code=404, detail="Purchase Order Item not found in this PO.")
    
    # Adjust total_amount on the PO and reduce inventory
    db_po.total_amount -= db_po_item.line_total
    db_po.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_po.updated_by = get_user_identifier(user)
    inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == db_po_item.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
    if inv:
        inv.current_stock = (inv.current_stock or 0) - db_po_item.quantity
        db.add(inv)

    db.delete(db_po_item)
    db.commit()
    db.refresh(db_po) # Refresh the PO to reflect updated total

    logger.info(f"Item ID {item_id} removed from Purchase Order (ID: {po_id}) by user {get_user_identifier(user)} for tenant {tenant_id}")
    return {"message": "Item removed successfully"}

class ReceiptUploadRequest(BaseModel):
    filename: str

@router.post("/{po_id}/receipt-upload-url")
def get_receipt_upload_url(
    po_id: int,
    request_body: ReceiptUploadRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a pre-signed URL for uploading a purchase order receipt."""
    if not generate_presigned_upload_url:
        raise HTTPException(status_code=501, detail="S3 upload functionality is not configured.")

    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    try:
        upload_data = generate_presigned_upload_url(
            tenant_id=tenant_id,
            object_id=po_id,
            filename=request_body.filename
        )
        
        db_po.payment_receipt = upload_data["s3_path"]
        db.commit()

        return {"upload_url": upload_data["upload_url"], "s3_path": upload_data["s3_path"]}

    except Exception as e:
        logger.exception(f"Failed to generate presigned URL for PO {po_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")

@router.get("/{po_id}/receipt-download-url")
def get_receipt_download_url(
    po_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a pre-signed URL for downloading a purchase order receipt."""
    if not generate_presigned_download_url:
        raise HTTPException(status_code=501, detail="S3 download functionality is not configured.")

    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    if not db_po or not db_po.payment_receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if not db_po.payment_receipt.startswith('s3://'):
        raise HTTPException(status_code=400, detail="Receipt is not stored in S3.")

    try:
        download_url = generate_presigned_download_url(s3_path=db_po.payment_receipt)
        return {"download_url": download_url}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to generate download URL for PO {po_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")
