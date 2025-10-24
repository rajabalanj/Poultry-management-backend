from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import logging
import os
import uuid
from utils.auth_utils import get_current_user, get_user_identifier, require_group
from utils.tenancy import get_tenant_id
from datetime import datetime
import pytz
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict
from pydantic import BaseModel

try:
    from utils.s3_utils import generate_presigned_upload_url, generate_presigned_download_url
except ImportError:
    generate_presigned_upload_url = None
    generate_presigned_download_url = None

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
    user: dict = Depends(require_group(["admin", "payment-group"])),
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

    db_payment = SalesPaymentModel(**payment.model_dump(), tenant_id=tenant_id, created_by=get_user_identifier(user))
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
    
    db_so.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_so.updated_by = get_user_identifier(user)
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
    user: dict = Depends(require_group(["admin", "payment-group"])),
    tenant_id: str = Depends(get_tenant_id)
):
    """Update an existing sales payment."""
    db_payment = db.query(SalesPaymentModel).filter(SalesPaymentModel.id == payment_id, SalesPaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Sales Payment not found")

    old_values = sqlalchemy_to_dict(db_payment)
    old_amount_paid = db_payment.amount_paid
    
    payment_data = payment_update.model_dump(exclude_unset=True)
    for key, value in payment_data.items():
        setattr(db_payment, key, value)
    
    db_payment.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_payment.updated_by = get_user_identifier(user)
    
    new_values = sqlalchemy_to_dict(db_payment)
    log_entry = AuditLogCreate(
        table_name='sales_payments',
        record_id=str(payment_id),
        changed_by=get_user_identifier(user),
        action='UPDATE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)
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

        db_so.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
        db_so.updated_by = get_user_identifier(user)
        db.commit()
        db.refresh(db_so)

    logger.info(f"Sales Payment ID {payment_id} updated for Sales Order ID {db_payment.sales_order_id} by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_payment

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sales_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin", "payment-group"])),
    tenant_id: str = Depends(get_tenant_id)
):
    """Delete a sales payment."""
    db_payment = db.query(SalesPaymentModel).filter(SalesPaymentModel.id == payment_id, SalesPaymentModel.tenant_id == tenant_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Sales Payment not found")

    db_so = db_payment.sales_order
    
    old_values = sqlalchemy_to_dict(db_payment)
    db_payment.deleted_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_payment.deleted_by = get_user_identifier(user)
    new_values = sqlalchemy_to_dict(db_payment)
    log_entry = AuditLogCreate(
        table_name='sales_payments',
        record_id=str(payment_id),
        changed_by=get_user_identifier(user),
        action='DELETE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)
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

        db_so.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
        db_so.updated_by = get_user_identifier(user)
        db.commit()

    logger.info(f"Sales Payment ID {payment_id} deleted for Sales Order ID {db_payment.sales_order_id}  by user {get_user_identifier(user)} for tenant {tenant_id}")
    return {"message": "Sales Payment deleted successfully"}

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

    db_payment = db.query(SalesPaymentModel).filter(SalesPaymentModel.id == payment_id, SalesPaymentModel.tenant_id == tenant_id).first()
    if not db_payment:
        raise HTTPException(status_code=404, detail="Sales Payment not found")

    try:
        upload_data = generate_presigned_upload_url(
            tenant_id=tenant_id,
            object_id=payment_id,
            filename=request_body.filename
        )
        
        # Save the final S3 path to the database immediately
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

    db_payment = db.query(SalesPaymentModel).filter(SalesPaymentModel.id == payment_id, SalesPaymentModel.tenant_id == tenant_id).first()
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