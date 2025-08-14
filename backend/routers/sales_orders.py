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
from models.vendors import Vendor as VendorModel
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
    db_vendor = db.query(VendorModel).filter(VendorModel.id == so.vendor_id, VendorModel.status == 'ACTIVE').first()
    if not db_vendor:
        raise HTTPException(status_code=400, detail="Customer not found or is inactive.")

    total_amount = Decimal(0)
    db_so_items = []

    if not so.items:
        raise HTTPException(status_code=400, detail="Sales order must contain at least one item.")

    for item_data in so.items:
        db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_data.inventory_item_id).first()
        if not db_inventory_item:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_data.inventory_item_id} not found.")
        
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
        vendor_id=so.vendor_id,
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
    
    db.commit()
    db.refresh(db_so)
    
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).filter(SalesOrderModel.id == db_so.id).first()

    logger.info(f"Sales Order (ID: {db_so.id}) created for Customer ID {db_so.vendor_id} by {x_user_id}")
    return db_so

@router.get("/", response_model=List[SalesOrderSchema])
def read_sales_orders(
    skip: int = 0,
    limit: int = 100,
    vendor_id: Optional[int] = None,
    status: Optional[SalesOrderStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Retrieve a list of sales orders with various filters."""
    query = db.query(SalesOrderModel)

    if vendor_id:
        query = query.filter(SalesOrderModel.vendor_id == vendor_id)
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
    
    # When status changes to SHIPPED, reduce inventory
    if so_update.status == SalesOrderStatus.SHIPPED and db_so.status != SalesOrderStatus.SHIPPED:
        logger.info(f"SO (ID: {so_id}) status changed to 'Shipped'. Inventory reduction logic would be triggered here.")

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

    if db_so.status not in [SalesOrderStatus.DRAFT, SalesOrderStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sales Order status is '{db_so.status.value}'. Only 'Draft' or 'Cancelled' SOs can be deleted."
        )

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