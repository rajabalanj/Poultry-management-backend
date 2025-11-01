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
from utils.receipt_utils import generate_sales_receipt

try:
    from utils.s3_utils import generate_presigned_download_url, upload_generated_receipt_to_s3
except ImportError:
    generate_presigned_download_url = None
    upload_generated_receipt_to_s3 = None

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
    """Record a new payment for a sales order and generate a receipt."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == payment.sales_order_id, SalesOrderModel.tenant_id == tenant_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found for this payment.")

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

    # Generate and upload receipt
    receipt_path = None
    try:
        logger.debug(f"Attempting to generate receipt for payment {db_payment.id}.")
        receipt_path = generate_sales_receipt(db, db_payment.id)
        logger.debug(f"Receipt generated at: {receipt_path}")

        if upload_generated_receipt_to_s3:
            logger.debug(f"S3 upload functionality is configured. Attempting to upload receipt {receipt_path} to S3.")
            s3_path = upload_generated_receipt_to_s3(tenant_id, db_payment.id, receipt_path)
            db_payment.payment_receipt = s3_path
            db.commit()
            db.refresh(db_payment)
            logger.debug(f"Receipt uploaded to S3: {s3_path} and payment_receipt field updated for payment {db_payment.id}.")
        else:
            logger.warning(f"S3 upload functionality is NOT configured. Receipt for payment {db_payment.id} will NOT be uploaded to S3 and payment_receipt field will remain None.")
    except Exception as e:
        logger.exception(f"Failed to generate or upload receipt for payment {db_payment.id}. Payment record still exists but receipt might be missing.")
        # Decide if you want to raise an error to the user or just log it
    finally:
        if receipt_path and os.path.exists(receipt_path):
            os.remove(receipt_path)
            logger.debug(f"Temporary receipt file removed: {receipt_path}")

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



@router.get("/{payment_id}/receipt-download-url")
def get_receipt_download_url(
    payment_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a pre-signed URL for downloading a payment receipt."""
    logger.debug(f"Attempting to get receipt download URL for payment_id: {payment_id}, tenant_id: {tenant_id}")

    if not generate_presigned_download_url:
        logger.warning(f"S3 download functionality is not configured for tenant_id: {tenant_id}. Raising 501.")
        raise HTTPException(status_code=501, detail="S3 download functionality is not configured.")

    db_payment = db.query(SalesPaymentModel).filter(SalesPaymentModel.id == payment_id, SalesPaymentModel.tenant_id == tenant_id).first()
    if not db_payment:
        logger.warning(f"Sales Payment with ID {payment_id} not found for tenant_id: {tenant_id}. Raising 404.")
        raise HTTPException(status_code=404, detail="Sales Payment not found")

    if not db_payment.payment_receipt:
        logger.warning(f"Sales Payment {payment_id} has no payment_receipt recorded for tenant_id: {tenant_id}. Raising 404.")
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    logger.debug(f"Payment {payment_id} payment_receipt value: {db_payment.payment_receipt}")
    if not db_payment.payment_receipt.startswith('s3://'):
        logger.warning(f"Payment {payment_id} receipt path '{db_payment.payment_receipt}' is not an S3 path for tenant_id: {tenant_id}. Raising 400.")
        raise HTTPException(status_code=400, detail="Receipt is not stored in S3.")

    try:
        download_url = generate_presigned_download_url(s3_path=db_payment.payment_receipt)
        logger.debug(f"Successfully generated download URL for payment {payment_id}.")
        return {"download_url": download_url}
    except FileNotFoundError as e:
        logger.error(f"S3 file not found for payment {payment_id} at path {db_payment.payment_receipt}: {e}", exc_info=True)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to generate download URL for payment {payment_id} for tenant_id: {tenant_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")