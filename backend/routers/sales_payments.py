from fastapi import APIRouter, Depends, HTTPException, Header, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from decimal import Decimal
import os
import uuid
from utils.auth_utils import get_current_user
from utils.auth_utils import get_user_identifier
from utils.tenancy import get_tenant_id

try:
    from utils.s3_upload import upload_receipt_to_s3
except ImportError:
    upload_receipt_to_s3 = None

from database import get_db
from models.sales_payments import SalesPayment as SalesPaymentModel
from models.sales_orders import SalesOrder as SalesOrderModel, SalesOrderStatus
from schemas.sales_payments import SalesPayment, SalesPaymentCreate, SalesPaymentUpdate

router = APIRouter(prefix="/sales-payments", tags=["Sales Payments"])
logger = logging.getLogger("sales_payments")

@router.post("/", response_model=SalesPayment, status_code=status.HTTP_201_CREATED)
def create_sales_payment(
    payment: SalesPaymentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Record a new payment for a sales order."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == payment.sales_order_id, SalesOrderModel.tenant_id == tenant_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found for this payment.")

    # No CANCELLED status present in enum; continue with payment logic

    remaining_amount = db_so.total_amount - db_so.total_amount_paid
    if payment.amount_paid > remaining_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount ({payment.amount_paid}) exceeds remaining due amount ({remaining_amount}) for SO {db_so.id}."
        )

    db_payment = SalesPaymentModel(**payment.model_dump(), tenant_id=tenant_id)
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    # Update total_amount_paid and SO status
    db_so.total_amount_paid += payment.amount_paid
    
    if db_so.total_amount_paid >= db_so.total_amount:
        db_so.status = SalesOrderStatus.PAID
        logger.info(f"SO {db_so.id} status updated to 'PAID' (fully paid).")
    elif db_so.total_amount_paid > 0:
        if db_so.status != SalesOrderStatus.PARTIALLY_PAID:
            db_so.status = SalesOrderStatus.PARTIALLY_PAID
            logger.info(f"SO {db_so.id} status updated to 'PARTIALLY_PAID'.")
    
    db.commit()
    db.refresh(db_payment)

    logger.info(f"Payment of {payment.amount_paid} recorded for Sales Order ID {payment.sales_order_id} by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_payment

@router.get("/by-so/{so_id}", response_model=List[SalesPayment])
def get_payments_for_so(so_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """Retrieve all payments for a specific sales order."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found.")
    
    payments = db.query(SalesPaymentModel).filter(SalesPaymentModel.sales_order_id == so_id, SalesPaymentModel.tenant_id == tenant_id).order_by(SalesPaymentModel.payment_date.asc()).all()
    return payments

@router.get("/{payment_id}", response_model=SalesPayment)
def read_sales_payment(payment_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """Retrieve a single sales payment by ID."""
    db_payment = db.query(SalesPaymentModel).filter(SalesPaymentModel.id == payment_id, SalesPaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Sales Payment not found")
    return db_payment

@router.patch("/{payment_id}", response_model=SalesPayment)
def update_sales_payment(
    payment_id: int,
    payment_update: SalesPaymentUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Update an existing sales payment."""
    db_payment = db.query(SalesPaymentModel).filter(SalesPaymentModel.id == payment_id, SalesPaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Sales Payment not found")

    old_amount_paid = db_payment.amount_paid
    
    payment_data = payment_update.model_dump(exclude_unset=True)
    for key, value in payment_data.items():
        setattr(db_payment, key, value)
    
    db.commit()
    db.refresh(db_payment)

    # Re-evaluate SO payment status if amount changed
    db_so = db_payment.sales_order
    if db_so and 'amount_paid' in payment_data:
        amount_difference = db_payment.amount_paid - old_amount_paid
        db_so.total_amount_paid += amount_difference
        
        if db_so.total_amount_paid >= db_so.total_amount:
            db_so.status = SalesOrderStatus.PAID
        elif db_so.total_amount_paid > 0:
            db_so.status = SalesOrderStatus.PARTIALLY_PAID
        else:
            db_so.status = SalesOrderStatus.DRAFT

        db.commit()
        db.refresh(db_so)

    logger.info(f"Sales Payment ID {payment_id} updated for Sales Order ID {db_payment.sales_order_id} by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_payment

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sales_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Delete a sales payment."""
    db_payment = db.query(SalesPaymentModel).filter(SalesPaymentModel.id == payment_id, SalesPaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Sales Payment not found")

    db_so = db_payment.sales_order
    
    db.delete(db_payment)
    db.commit()

    # Re-evaluate SO payment status after deletion
    if db_so:
        db_so.total_amount_paid -= db_payment.amount_paid

        if db_so.total_amount_paid >= db_so.total_amount:
            db_so.status = SalesOrderStatus.PAID
        elif db_so.total_amount_paid > 0:
            db_so.status = SalesOrderStatus.PARTIALLY_PAID
        else:
            db_so.status = SalesOrderStatus.DRAFT

        db.commit()

    logger.info(f"Sales Payment ID {payment_id} deleted for Sales Order ID {db_payment.sales_order_id}  by user {get_user_identifier(user)} for tenant {tenant_id}")
    return {"message": "Sales Payment deleted successfully"}

@router.post("/{payment_id}/receipt")
def upload_payment_receipt(
    payment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Upload payment receipt for a sales payment."""
    db_payment = db.query(SalesPaymentModel).filter(SalesPaymentModel.id == payment_id, SalesPaymentModel.tenant_id == tenant_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Sales Payment not found")
    
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PDF and image files allowed")
    
    upload_dir = f"uploads/sales_payment_receipts/{tenant_id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"sales_payment_{payment_id}_{uuid.uuid4().hex}.{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    content = file.file.read()
    
    if os.getenv('AWS_ENVIRONMENT') and upload_receipt_to_s3:
        try:
            s3_url = upload_receipt_to_s3(content, file.filename, payment_id, tenant_id)
            db_payment.payment_receipt = s3_url
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to upload to S3")
    else:
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        db_payment.payment_receipt = file_path
    
    db.commit()
    return {"message": "Receipt uploaded successfully", "file_path": db_payment.payment_receipt}