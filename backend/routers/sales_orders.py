from fastapi import APIRouter, Depends, HTTPException, Header, status, UploadFile, File
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
import os
import uuid

try:
    from utils.s3_upload import upload_receipt_to_s3
except ImportError:
    upload_receipt_to_s3 = None

from database import get_db
from models.sales_orders import SalesOrder as SalesOrderModel, SalesOrderStatus
from models.sales_order_items import SalesOrderItem as SalesOrderItemModel
from models.inventory_items import InventoryItem as InventoryItemModel
from models.business_partners import BusinessPartner as BusinessPartnerModel
from models.sales_payments import SalesPayment as SalesPaymentModel
from schemas.sales_orders import (
    SalesOrder as SalesOrderSchema,
    SalesOrderCreate,
    SalesOrderUpdate,
    SalesOrderItem as SalesOrderItemSchema,
)
from schemas.sales_order_items import SalesOrderItemCreateRequest, SalesOrderItemUpdate

router = APIRouter(prefix="/sales-orders", tags=["Sales Orders"])
logger = logging.getLogger("sales_orders")

@router.post("/", response_model=SalesOrderSchema, status_code=status.HTTP_201_CREATED)
def create_sales_order(
    so: SalesOrderCreate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Create a new sales order with associated items."""
    db_customer = db.query(BusinessPartnerModel).filter(
        BusinessPartnerModel.id == so.customer_id, 
        BusinessPartnerModel.status == 'ACTIVE',
        BusinessPartnerModel.is_customer == True
    ).first()
    if not db_customer:
        raise HTTPException(status_code=400, detail="Business partner not found, inactive, or not a customer.")

    total_amount = Decimal(0)
    db_so_items = []

    if not so.items:
        raise HTTPException(status_code=400, detail="Sales order must contain at least one item.")

    for item_data in so.items:
        db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_data.inventory_item_id).first()
        if not db_inventory_item:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_data.inventory_item_id} not found.")
        # Ensure there is enough stock to fulfill this sales order item
        if db_inventory_item.current_stock is not None and db_inventory_item.current_stock < item_data.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{db_inventory_item.name}'. Available: {db_inventory_item.current_stock}, Requested: {item_data.quantity}")
        
        line_total = item_data.quantity * item_data.price_per_unit
        total_amount += line_total
        
        db_so_items.append(
            SalesOrderItemModel(
                inventory_item_id=item_data.inventory_item_id,
                quantity=item_data.quantity,
                price_per_unit=item_data.price_per_unit,
                line_total=line_total
            )
        )
    
    db_so = SalesOrderModel(
        customer_id=so.customer_id,
        order_date=so.order_date,
        status=so.status,
        notes=so.notes,
        total_amount=total_amount,
        created_by=x_user_id
    )
    db.add(db_so)
    db.flush()

    for item in db_so_items:
        item.sales_order_id = db_so.id
        db.add(item)
    # Deduct inventory immediately for each sales order item
    for item in db_so_items:
        inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item.inventory_item_id).with_for_update().first()
        if inv is None:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item.inventory_item_id} not found when updating stock.")
        if inv.current_stock is None or inv.current_stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{getattr(inv, 'name', item.inventory_item_id)}'. Available: {inv.current_stock}, Required: {item.quantity}")
        inv.current_stock -= item.quantity
        db.add(inv)
    
    db.commit()
    db.refresh(db_so)
    
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).filter(SalesOrderModel.id == db_so.id).first()

    logger.info(f"Sales Order (ID: {db_so.id}) created for Customer ID {db_so.customer_id} by {x_user_id}")
    return db_so

@router.get("/", response_model=List[SalesOrderSchema])
def read_sales_orders(
    skip: int = 0,
    limit: int = 100,
    customer_id: Optional[int] = None,
    status: Optional[SalesOrderStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Retrieve a list of sales orders with various filters."""
    query = db.query(SalesOrderModel)

    if customer_id:
        query = query.filter(SalesOrderModel.customer_id == customer_id)
    if status:
        query = query.filter(SalesOrderModel.status == status)
    if start_date:
        query = query.filter(SalesOrderModel.order_date >= start_date)
    if end_date:
        query = query.filter(SalesOrderModel.order_date <= end_date)

    sales_orders = query.options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).offset(skip).limit(limit).all()
    
    return sales_orders

@router.get("/{so_id}", response_model=SalesOrderSchema)
def read_sales_order(so_id: int, db: Session = Depends(get_db)):
    """Retrieve a single sales order by ID."""
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).filter(SalesOrderModel.id == so_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found")
    return db_so

@router.patch("/{so_id}", response_model=SalesOrderSchema)
def update_sales_order(
    so_id: int,
    so_update: SalesOrderUpdate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Update an existing sales order."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found")
    
    # Note: SHIPPED and CANCELLED statuses are not set anywhere in backend.
    # Keep status changes minimal here; payments update payment-related statuses (PAID/PARTIALLY_PAID/APPROVED/DRAFT).
    # No inventory changes are handled here for SHIPPED because the backend does not transition to SHIPPED.

    so_data = so_update.model_dump(exclude_unset=True)
    so_data.pop("total_amount", None)

    for key, value in so_data.items():
        setattr(db_so, key, value)
    
    db.commit()
    db.refresh(db_so)
    
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).filter(SalesOrderModel.id == so_id).first()
    
    logger.info(f"Sales Order (ID: {so_id}) updated by {x_user_id}")
    return db_so


@router.post("/{so_id}/items", response_model=SalesOrderSchema, status_code=status.HTTP_201_CREATED)
def add_item_to_sales_order(
    so_id: int,
    item_request: SalesOrderItemCreateRequest,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Add a new item to an existing sales order."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id).first()
    if not db_so:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    # Restrict adding items based on SO status (only prevent adding when fully paid)
    if db_so.status == SalesOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot add items to a sales order with status '{db_so.status.value}'.")

    # Validate that the inventory item exists
    db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_request.inventory_item_id).first()
    if not db_inventory_item:
        raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_request.inventory_item_id} not found.")

    # Critical for sales: Check if there is enough stock
    if db_inventory_item.current_stock < item_request.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{db_inventory_item.name}'. Available: {db_inventory_item.current_stock}, Requested: {item_request.quantity}")

    # Check if item already exists in this SO to prevent duplicates
    existing_item = db.query(SalesOrderItemModel).filter(
        SalesOrderItemModel.sales_order_id == so_id,
        SalesOrderItemModel.inventory_item_id == item_request.inventory_item_id
    ).first()
    if existing_item:
        raise HTTPException(status_code=400, detail="This item already exists in this sales order. Use the update endpoint to change quantity.")

    line_total = item_request.quantity * item_request.price_per_unit
    db_so_item = SalesOrderItemModel(
        sales_order_id=so_id,
        inventory_item_id=item_request.inventory_item_id,
        quantity=item_request.quantity,
        price_per_unit=item_request.price_per_unit,
        line_total=line_total
    )
    db.add(db_so_item)
    
    # Update the total_amount on the parent Sales Order
    db_so.total_amount += line_total
    # Deduct inventory for this added item
    inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_request.inventory_item_id).with_for_update().first()
    if inv is None:
        raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_request.inventory_item_id} not found when updating stock.")
    if inv.current_stock is None or inv.current_stock < item_request.quantity:
        raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{getattr(inv, 'name', item_request.inventory_item_id)}'. Available: {inv.current_stock}, Required: {item_request.quantity}")
    inv.current_stock -= item_request.quantity
    db.add(inv)
    
    db.commit()
    db.refresh(db_so)

    # Re-query with relationships for a complete response object
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items).selectinload(SalesOrderItemModel.inventory_item),
        selectinload(SalesOrderModel.payments),
        selectinload(SalesOrderModel.customer)
    ).filter(SalesOrderModel.id == so_id).first()

    logger.info(f"Item {db_inventory_item.name} added to Sales Order (ID: {so_id}) by {x_user_id}")
    return db_so


@router.patch("/{so_id}/items/{item_id}", response_model=SalesOrderSchema)
def update_sales_order_item(
    so_id: int,
    item_id: int,
    item_update: SalesOrderItemUpdate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
):
    """Update a specific item in a sales order."""
    db_so = (
        db.query(SalesOrderModel)
        .options(selectinload(SalesOrderModel.items))
        .filter(SalesOrderModel.id == so_id)
        .first()
    )
    if not db_so:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    item_to_update = None
    for item in db_so.items:
        if item.id == item_id:
            item_to_update = item
            break

    if not item_to_update:
        raise HTTPException(status_code=404, detail="Sales Order Item not found")

    # Do not allow item updates for finalized sales orders
    if db_so.status == SalesOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot modify items for a sales order with status '{db_so.status.value}'.")

    # Capture old quantity then apply updates and adjust inventory by the delta
    old_qty = item_to_update.quantity
    update_data = item_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item_to_update, key, value)

    # Recalculate line total and order total amount
    item_to_update.line_total = item_to_update.quantity * item_to_update.price_per_unit
    # Adjust inventory by the difference
    new_qty = item_to_update.quantity
    delta = new_qty - old_qty
    if delta != 0:
        inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_to_update.inventory_item_id).with_for_update().first()
        if inv is None:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_to_update.inventory_item_id} not found when updating stock.")
        if delta > 0:
            # Need more stock
            if inv.current_stock is None or inv.current_stock < delta:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{getattr(inv, 'name', item_to_update.inventory_item_id)}'. Available: {inv.current_stock}, Required additional: {delta}")
            inv.current_stock -= delta
        else:
            # Returned/reduced quantity -> restore stock
            inv.current_stock = (inv.current_stock or 0) + (-delta)
        db.add(inv)

    total_amount = sum(item.line_total for item in db_so.items)
    db_so.total_amount = total_amount

    db.commit()
    db.refresh(db_so)

    logger.info(
        f"Sales Order Item (ID: {item_id}) of Sales Order (ID: {so_id}) updated by {x_user_id}"
    )
    return db_so


@router.delete("/{so_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Delete a sales order."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    if db_so.status != SalesOrderStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sales Order status is '{db_so.status.value}'. Only 'Draft' SOs can be deleted."
        )

    # Restore inventory for items on the deleted sales order
    for item in db_so.items:
        inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item.inventory_item_id).with_for_update().first()
        if inv:
            inv.current_stock = (inv.current_stock or 0) + item.quantity
            db.add(inv)
    db.delete(db_so)
    db.commit()
    logger.info(f"Sales Order (ID: {so_id}) deleted by {x_user_id}")
    return {"message": "Sales Order deleted successfully"}

@router.post("/{so_id}/receipt")
def upload_payment_receipt(
    so_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload payment receipt for a sales order."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id).first()
    if not db_so:
        raise HTTPException(status_code=404, detail="Sales Order not found")
    
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PDF and image files allowed")
    
    upload_dir = "uploads/sales_receipts"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{so_id}_{uuid.uuid4().hex}.{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    content = file.file.read()
    
    if os.getenv('AWS_ENVIRONMENT') and upload_receipt_to_s3:
        try:
            s3_url = upload_receipt_to_s3(content, file.filename, so_id)
            db_so.payment_receipt = s3_url
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to upload to S3")
    else:
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        db_so.payment_receipt = file_path
    
    db.commit()
    return {"message": "Receipt uploaded successfully", "file_path": db_so.payment_receipt}
