# backend/routers/purchase_orders.py

from fastapi import APIRouter, Depends, HTTPException, Header, status, UploadFile, File
from sqlalchemy.orm import Session, selectinload # <-- import selectinload
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
from schemas.purchase_order_items import PurchaseOrderItemUpdate

from database import get_db
from models.purchase_orders import PurchaseOrder as PurchaseOrderModel, PurchaseOrderStatus
from models.purchase_order_items import PurchaseOrderItem as PurchaseOrderItemModel
from models.inventory_items import InventoryItem as InventoryItemModel
from models.vendors import Vendor as VendorModel
from models.payments import Payment as PaymentModel # Import the Payment model
from schemas.purchase_orders import (
    PurchaseOrder as PurchaseOrderSchema,
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderItem as PurchaseOrderItemSchema,
    PurchaseOrderItemCreateRequest,
)

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])
logger = logging.getLogger("purchase_orders")

# ... (other endpoints like create_purchase_order, get_purchase_orders, etc.)

@router.get("/{po_id}", response_model=PurchaseOrderSchema)
def get_purchase_order(
    po_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve a single purchase order by ID, with all related details."""
    db_po = (
        db.query(PurchaseOrderModel)
        .filter(PurchaseOrderModel.id == po_id)
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
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Create a new purchase order with associated items."""
    # 1. Validate Vendor
    db_vendor = db.query(VendorModel).filter(VendorModel.id == po.vendor_id, VendorModel.status == 'ACTIVE').first()
    if not db_vendor:
        raise HTTPException(status_code=400, detail="Vendor not found or is inactive.")

    total_amount = Decimal(0)
    db_po_items = []

    # 3. Prepare Purchase Order Items and calculate total
    if not po.items:
        raise HTTPException(status_code=400, detail="Purchase order must contain at least one item.")

    for item_data in po.items:
        db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_data.inventory_item_id).first()
        if not db_inventory_item:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_data.inventory_item_id} not found.")
        
        line_total = item_data.quantity * item_data.price_per_unit
        total_amount += line_total
        
        db_po_items.append(
            PurchaseOrderItemModel(
                inventory_item_id=item_data.inventory_item_id,
                quantity=item_data.quantity,
                price_per_unit=item_data.price_per_unit,
                line_total=line_total
            )
        )
    
    # 4. Create the Purchase Order
    db_po = PurchaseOrderModel(
        vendor_id=po.vendor_id,
        order_date=po.order_date,
        status=po.status,
        notes=po.notes,
        total_amount=total_amount,
        created_by=x_user_id
    )
    db.add(db_po)
    db.flush() # Flush to get db_po.id before adding items

    for item in db_po_items:
        item.purchase_order_id = db_po.id
        db.add(item)
    
    db.commit()
    db.refresh(db_po)
    
    # Refresh with relationships for the response
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).filter(PurchaseOrderModel.id == db_po.id).first()

    logger.info(f"Purchase Order (ID: {db_po.id}) created for Vendor ID {db_po.vendor_id} by {x_user_id}")
    return db_po

@router.get("/", response_model=List[PurchaseOrderSchema])
def read_purchase_orders(
    skip: int = 0,
    limit: int = 100,
    vendor_id: Optional[int] = None,
    status: Optional[PurchaseOrderStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Retrieve a list of purchase orders with various filters."""
    query = db.query(PurchaseOrderModel)

    if vendor_id:
        query = query.filter(PurchaseOrderModel.vendor_id == vendor_id)
    if status:
        query = query.filter(PurchaseOrderModel.status == status)
    if start_date:
        query = query.filter(PurchaseOrderModel.order_date >= start_date)
    if end_date:
        query = query.filter(PurchaseOrderModel.order_date <= end_date)

    # Eagerly load items and payments for the response model
    purchase_orders = query.options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).offset(skip).limit(limit).all()
    
    return purchase_orders

@router.get("/{po_id}", response_model=PurchaseOrderSchema)
def read_purchase_order(po_id: int, db: Session = Depends(get_db)):
    """Retrieve a single purchase order by ID."""
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).filter(PurchaseOrderModel.id == po_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    return db_po

@router.patch("/{po_id}", response_model=PurchaseOrderSchema)
def update_purchase_order(
    po_id: int,
    po_update: PurchaseOrderUpdate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Update an existing purchase order (partial update).
    Note: Item additions/removals are handled via separate endpoints."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    # If status is changing to 'Received', trigger inventory update (not fully implemented here)
    if po_update.status == PurchaseOrderStatus.PAID and db_po.status != PurchaseOrderStatus.PAID:
        # Here you would typically call a service/function to update inventory
        # For this example, we'll just log it.
        logger.info(f"PO (ID: {po_id}) status changed to 'Paid'. Inventory update logic would be triggered here.")
        # Example of how you might update stock (simplified, needs error handling and atomicity)
        # for item in db_po.items:
        #     db_inventory_item = db.query(InventoryItemModel).get(item.inventory_item_id)
        #     if db_inventory_item:
        #         db_inventory_item.current_stock += item.quantity
        #         # Recalculate average cost if needed
        #         # db_inventory_item.average_cost = (old_stock * old_avg_cost + new_qty * new_price) / (old_stock + new_qty)
        #         db.add(db_inventory_item)
        # db.commit() # Commit inventory changes
        # db.refresh(db_po) # Refresh PO after inventory update


    po_data = po_update.model_dump(exclude_unset=True)
    # Prevent direct update of total_amount
    po_data.pop("total_amount", None) 

    for key, value in po_data.items():
        setattr(db_po, key, value)
    
    db.commit()
    db.refresh(db_po)
    
    # Refresh with relationships for the response
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).filter(PurchaseOrderModel.id == po_id).first()
    
    logger.info(f"Purchase Order (ID: {po_id}) updated by {x_user_id}")
    return db_po

@router.delete("/{po_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Delete a purchase order. Only DRAFT or CANCELLED POs can be fully deleted.
    Others should be cancelled (status change)."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    if db_po.status not in [PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Purchase Order status is '{db_po.status.value}'. Only 'Draft' or 'Cancelled' POs can be hard deleted. Consider changing status to 'Cancelled' instead."
        )
    
    # If PO has been received (even partially), deleting it would affect inventory.
    # This logic would need to reverse inventory updates or be strictly prevented.
    # For now, we assume this strict check is enough.
    if db_po.status in [PurchaseOrderStatus.PARTIALLY_PAID, PurchaseOrderStatus.PAID]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a purchase order that has been partially or fully received. Change status to 'Cancelled' instead."
        )

    db.delete(db_po)
    db.commit()
    logger.info(f"Purchase Order (ID: {po_id}) hard deleted by {x_user_id}")
    return {"message": "Purchase Order deleted successfully"}

# --- Purchase Order Item Endpoints (Nested for managing items within a PO) ---

@router.post("/{po_id}/items", response_model=PurchaseOrderSchema, status_code=status.HTTP_201_CREATED)
def add_item_to_purchase_order(
    po_id: int,
    item_request: PurchaseOrderItemCreateRequest,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Add a new item to an existing purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    # Restrict item modification based on PO status (e.g., cannot add if 'Received')
    if db_po.status in [PurchaseOrderStatus.PAID, PurchaseOrderStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"Cannot add items to a purchase order with status '{db_po.status.value}'.")

    db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_request.inventory_item_id).first()
    if not db_inventory_item:
        raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_request.inventory_item_id} not found.")

    # Check if item already exists in PO (optional: prevent duplicates or update existing)
    existing_item = db.query(PurchaseOrderItemModel).filter(
        PurchaseOrderItemModel.purchase_order_id == po_id,
        PurchaseOrderItemModel.inventory_item_id == item_request.inventory_item_id
    ).first()
    if existing_item:
        raise HTTPException(status_code=400, detail="This item already exists in this purchase order. Use PATCH to update quantity.")

    line_total = item_request.quantity * item_request.price_per_unit
    db_po_item = PurchaseOrderItemModel(
        purchase_order_id=po_id,
        inventory_item_id=item_request.inventory_item_id,
        quantity=item_request.quantity,
        price_per_unit=item_request.price_per_unit,
        line_total=line_total
    )
    db.add(db_po_item)
    
    # Update total_amount on the PO
    db_po.total_amount += line_total
    
    db.commit()
    db.refresh(db_po)

    # Refresh with relationships for the response
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).filter(PurchaseOrderModel.id == po_id).first()

    logger.info(f"Item added to Purchase Order (ID: {po_id}) by {x_user_id}")
    return db_po

@router.patch("/{po_id}/items/{item_id}", response_model=PurchaseOrderSchema)
def update_item_in_purchase_order(
    po_id: int,
    item_id: int,
    item_update: PurchaseOrderItemUpdate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Update an item's quantity or price in a purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    if db_po.status in [PurchaseOrderStatus.PAID, PurchaseOrderStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"Cannot update items in a purchase order with status '{db_po.status.value}'.")

    db_po_item = db.query(PurchaseOrderItemModel).filter(
        PurchaseOrderItemModel.id == item_id,
        PurchaseOrderItemModel.purchase_order_id == po_id
    ).first()
    if db_po_item is None:
        raise HTTPException(status_code=404, detail="Purchase Order Item not found in this PO.")

    old_line_total = db_po_item.line_total
    
    item_data = item_update.model_dump(exclude_unset=True)
    for key, value in item_data.items():
        setattr(db_po_item, key, value)
    
    db_po_item.line_total = db_po_item.quantity * db_po_item.price_per_unit
    db_po.total_amount += (db_po_item.line_total - old_line_total) # Adjust PO total

    db.commit()
    db.refresh(db_po_item)
    db.refresh(db_po) # Refresh the PO to reflect updated total

    # Refresh with relationships for the response
    db_po = db.query(PurchaseOrderModel).options(
        selectinload(PurchaseOrderModel.items),
        selectinload(PurchaseOrderModel.payments)
    ).filter(PurchaseOrderModel.id == po_id).first()

    logger.info(f"Item ID {item_id} in Purchase Order (ID: {po_id}) updated by {x_user_id}")
    return db_po

@router.delete("/{po_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item_from_purchase_order(
    po_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Remove an item from a purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    if db_po.status in [PurchaseOrderStatus.PAID, PurchaseOrderStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"Cannot remove items from a purchase order with status '{db_po.status.value}'.")
        
    db_po_item = db.query(PurchaseOrderItemModel).filter(
        PurchaseOrderItemModel.id == item_id,
        PurchaseOrderItemModel.purchase_order_id == po_id
    ).first()
    if db_po_item is None:
        raise HTTPException(status_code=404, detail="Purchase Order Item not found in this PO.")
    
    # Adjust total_amount on the PO
    db_po.total_amount -= db_po_item.line_total

    db.delete(db_po_item)
    db.commit()
    db.refresh(db_po) # Refresh the PO to reflect updated total

    logger.info(f"Item ID {item_id} removed from Purchase Order (ID: {po_id}) by {x_user_id}")
    return {"message": "Item removed successfully"}

@router.post("/{po_id}/receipt")
def upload_payment_receipt(
    po_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload payment receipt for a purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id).first()
    if not db_po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    # Validate file type
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PDF and image files allowed")
    
    # Create uploads directory
    upload_dir = "uploads/receipts"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{po_id}_{uuid.uuid4().hex}.{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # Read and save file
    content = file.file.read()
    
    if os.getenv('AWS_ENVIRONMENT') and upload_receipt_to_s3:
        try:
            s3_url = upload_receipt_to_s3(content, file.filename, po_id)
            db_po.payment_receipt = s3_url
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to upload to S3")
    else:
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        db_po.payment_receipt = file_path
    
    db.commit()
    return {"message": "Receipt uploaded successfully", "file_path": db_po.payment_receipt}