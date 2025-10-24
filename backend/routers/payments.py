from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import logging
import os
import uuid
from utils.auth_utils import get_current_user, get_user_identifier, require_group
from utils.tenancy import get_tenant_id
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict
from datetime import datetime
import pytz
from pydantic import BaseModel

try:
    from utils.s3_utils import generate_presigned_upload_url, generate_presigned_download_url
except ImportError:
    generate_presigned_upload_url = None
    generate_presigned_download_url = None

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
    user: dict = Depends(require_group(["admin", "payment-group"])),
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

    db_payment = PaymentModel(**payment.model_dump(), tenant_id=tenant_id, created_by=get_user_identifier(user))
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

    logger.info(f"Payment of {payment.amount_paid} recorded for Purchase Order ID {payment.purchase_order_id} by user {get_user_identifier(user)} for tenant {tenant_id}")
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
    user: dict = Depends(require_group(["admin", "payment-group"])),
    tenant_id: str = Depends(get_tenant_id)
):
    """Update an existing payment."""
    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id, PaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    old_values = sqlalchemy_to_dict(db_payment)
    old_amount_paid = db_payment.amount_paid # Store old amount for PO total recalculation
    
    payment_data = payment_update.model_dump(exclude_unset=True)
    for key, value in payment_data.items():
        setattr(db_payment, key, value)
    
    db_payment.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_payment.updated_by = get_user_identifier(user)
    
    new_values = sqlalchemy_to_dict(db_payment)
    log_entry = AuditLogCreate(
        table_name='payments',
        record_id=str(payment_id),
        changed_by=get_user_identifier(user),
        action='UPDATE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)
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

    logger.info(f"Payment ID {payment_id} updated for Purchase Order ID {db_payment.purchase_order_id} by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_payment

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin", "payment-group"])),
    tenant_id: str = Depends(get_tenant_id)
):
    """Delete a payment."""
    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id, PaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    db_po = db_payment.purchase_order # Get the related PO
    
    old_values = sqlalchemy_to_dict(db_payment)
    db_payment.deleted_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_payment.deleted_by = get_user_identifier(user)
    new_values = sqlalchemy_to_dict(db_payment)
    log_entry = AuditLogCreate(
        table_name='payments',
        record_id=str(payment_id),
        changed_by=get_user_identifier(user),
        action='DELETE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)
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

    logger.info(f"Payment ID {payment_id} deleted for Purchase Order ID {db_payment.purchase_order_id} by user {get_user_identifier(user)} for tenant {tenant_id}")
    return {"message": "Payment deleted successfully"}

class ReceiptUploadRequest(BaseModel):
    filename: str

@router.post("/{payment_id}/receipt-upload-url")
def get_receipt_upload_url(
    payment_id: int,
    request_body: ReceiptUploadRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin", "payment-group"])),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a pre-signed URL for uploading a payment receipt."""
    if not generate_presigned_upload_url:
        raise HTTPException(status_code=501, detail="S3 upload functionality is not configured.")

    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id, PaymentModel.tenant_id == tenant_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    try:
        upload_data = generate_presigned_upload_url(
            tenant_id=tenant_id,
            object_id=payment_id,
            filename=request_body.filename
        )
        
        db_payment.payment_receipt = upload_data["s3_path"]
        db.commit()

        return {"upload_url": upload_data["upload_url"], "s3_path": upload_data["s3_path"]}

    except Exception as e:
        logger.exception(f"Failed to generate presigned URL for payment {payment_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")

@router.get("/{payment_id}/receipt-download-url")
def get_receipt_download_url(
    payment_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a pre-signed URL for downloading a payment receipt."""
    if not generate_presigned_download_url:
        raise HTTPException(status_code=501, detail="S3 download functionality is not configured.")

    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id, PaymentModel.tenant_id == tenant_id).first()
    if not db_payment or not db_payment.payment_receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if not db_payment.payment_receipt.startswith('s3://'):
        raise HTTPException(status_code=400, detail="Receipt is not stored in S3.")

    try:
        download_url = generate_presigned_download_url(s3_path=db_payment.payment_receipt)
        return {"download_url": download_url}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to generate download URL for payment {payment_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")
