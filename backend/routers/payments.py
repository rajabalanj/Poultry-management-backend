from fastapi import APIRouter, Depends, HTTPException, Header, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from decimal import Decimal
import os
import uuid
from utils.auth_utils import get_current_user
from utils.tenancy import get_tenant_id

try:
    from utils.s3_upload import upload_receipt_to_s3
except ImportError:
    upload_receipt_to_s3 = None

from database import get_db
from models.payments import Payment as PaymentModel
from models.purchase_orders import PurchaseOrder as PurchaseOrderModel, PurchaseOrderStatus
from schemas.payments import Payment, PaymentCreate, PaymentUpdate

router = APIRouter(prefix="/payments", tags=["Payments"])
logger = logging.getLogger("payments")

@router.post("/", response_model=Payment, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment: PaymentCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Record a new payment for a purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == payment.purchase_order_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found for this payment.")

    # No explicit CANCELLED status in enum; payments route controls PAID/PARTIALLY_PAID/APPROVED/DRAFT

    # Check if payment exceeds remaining amount
    remaining_amount = db_po.total_amount - db_po.total_amount_paid
    if payment.amount_paid > remaining_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount ({payment.amount_paid}) exceeds remaining due amount ({remaining_amount}) for PO {db_po.id}."
        )

    db_payment = PaymentModel(**payment.model_dump(), tenant_id=tenant_id)
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    # Update total_amount_paid and PO status
    db_po.total_amount_paid += payment.amount_paid
    
    if db_po.total_amount_paid >= db_po.total_amount:
        db_po.status = PurchaseOrderStatus.PAID
        logger.info(f"PO {db_po.id} status updated to 'PAID' (fully paid).")
    elif db_po.total_amount_paid > 0:
        if db_po.status != PurchaseOrderStatus.PARTIALLY_PAID:
            db_po.status = PurchaseOrderStatus.PARTIALLY_PAID
            logger.info(f"PO {db_po.id} status updated to 'PARTIALLY_PAID'.")
    
    db.commit() # Commit PO status update
    db.refresh(db_payment) # Re-refresh payment to ensure everything is in sync for response

    logger.info(f"Payment of {payment.amount_paid} recorded for Purchase Order ID {payment.purchase_order_id} by user {user.get('sub')} for tenant {tenant_id}")
    return db_payment

@router.get("/by-po/{po_id}", response_model=List[Payment])
def get_payments_for_po(po_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """Retrieve all payments for a specific purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id, PurchaseOrderModel.tenant_id == tenant_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found.")
    
    payments = db.query(PaymentModel).filter(PaymentModel.purchase_order_id == po_id, PaymentModel.tenant_id == tenant_id).order_by(PaymentModel.payment_date.asc()).all()
    return payments

@router.get("/{payment_id}", response_model=Payment)
def read_payment(payment_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """Retrieve a single payment by ID."""
    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id, PaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return db_payment

@router.patch("/{payment_id}", response_model=Payment)
def update_payment(
    payment_id: int,
    payment_update: PaymentUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Update an existing payment."""
    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id, PaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    old_amount_paid = db_payment.amount_paid # Store old amount for PO total recalculation
    
    payment_data = payment_update.model_dump(exclude_unset=True)
    for key, value in payment_data.items():
        setattr(db_payment, key, value)
    
    db.commit()
    db.refresh(db_payment)

    # Re-evaluate PO payment status and total if amount changed
    db_po = db_payment.purchase_order
    if db_po and 'amount_paid' in payment_data:
        amount_difference = db_payment.amount_paid - old_amount_paid
        db_po.total_amount_paid += amount_difference
        
        if db_po.total_amount_paid >= db_po.total_amount:
            db_po.status = PurchaseOrderStatus.PAID
        elif db_po.total_amount_paid > 0:
            db_po.status = PurchaseOrderStatus.PARTIALLY_PAID
        else:
            db_po.status = PurchaseOrderStatus.DRAFT

        db.commit()
        db.refresh(db_po)

    logger.info(f"Payment ID {payment_id} updated for Purchase Order ID {db_payment.purchase_order_id} by user {user.get('sub')} for tenant {tenant_id}")
    return db_payment

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Delete a payment."""
    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id, PaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    db_po = db_payment.purchase_order # Get the related PO
    
    db.delete(db_payment)
    db.commit()

    # Re-evaluate PO payment status after deletion
    if db_po:
        db_po.total_amount_paid -= db_payment.amount_paid

        if db_po.total_amount_paid >= db_po.total_amount:
            db_po.status = PurchaseOrderStatus.PAID
        elif db_po.total_amount_paid > 0:
            db_po.status = PurchaseOrderStatus.PARTIALLY_PAID
        else:
            db_po.status = PurchaseOrderStatus.DRAFT

        db.commit()

    logger.info(f"Payment ID {payment_id} deleted for Purchase Order ID {db_payment.purchase_order_id} by user {user.get('sub')} for tenant {tenant_id}")
    return {"message": "Payment deleted successfully"}

@router.post("/{payment_id}/receipt")
def upload_payment_receipt(
    payment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Upload payment receipt for a payment."""
    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id, PaymentModel.tenant_id == tenant_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    # Validate file type
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PDF and image files allowed")
    
    # Create uploads directory
    upload_dir = f"uploads/payment_receipts/{tenant_id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"payment_{payment_id}_{uuid.uuid4().hex}.{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # Read and save file
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