from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from decimal import Decimal

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
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Record a new payment for a purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == payment.purchase_order_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found for this payment.")

    # Prevent payments on cancelled POs
    if db_po.status == PurchaseOrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot record payments for a cancelled purchase order.")

    # Calculate current paid amount for the PO
    current_paid_amount = sum([p.amount_paid for p in db_po.payments]) if db_po.payments else Decimal(0)
    
    # Check if payment exceeds remaining amount
    remaining_amount = db_po.total_amount - current_paid_amount
    if payment.amount_paid > remaining_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Payment amount ({payment.amount_paid}) exceeds remaining due amount ({remaining_amount}) for PO {db_po.po_number}."
        )

    db_payment = PaymentModel(**payment.model_dump())
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    # Update PO status based on payment (if needed, this could be a separate function/trigger)
    # Re-calculate paid amount after new payment
    db.refresh(db_po) # Refresh PO to get the newly added payment in its relationship
    updated_paid_amount = sum([p.amount_paid for p in db_po.payments])
    
    if updated_paid_amount >= db_po.total_amount:
        db_po.status = PurchaseOrderStatus.PAID # Or a new status like 'Paid' if you want that distinction
        logger.info(f"PO {db_po.po_number} status updated to 'PAID' (fully paid).")
    elif updated_paid_amount > 0 and updated_paid_amount < db_po.total_amount:
        # If PO status isn't already 'Partially Received', update it
        if db_po.status != PurchaseOrderStatus.PARTIALLY_PAID:
            db_po.status = PurchaseOrderStatus.PARTIALLY_PAID
            logger.info(f"PO {db_po.po_number} status updated to 'PARTIALLY_PAID'.")
    
    db.commit() # Commit PO status update
    db.refresh(db_payment) # Re-refresh payment to ensure everything is in sync for response

    logger.info(f"Payment of {payment.amount_paid} recorded for Purchase Order ID {payment.purchase_order_id} by {x_user_id}")
    return db_payment

@router.get("/by-po/{po_id}", response_model=List[Payment])
def get_payments_for_po(po_id: int, db: Session = Depends(get_db)):
    """Retrieve all payments for a specific purchase order."""
    db_po = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.id == po_id).first()
    if db_po is None:
        raise HTTPException(status_code=404, detail="Purchase Order not found.")
    
    payments = db.query(PaymentModel).filter(PaymentModel.purchase_order_id == po_id).order_by(PaymentModel.payment_date.asc()).all()
    return payments

@router.get("/{payment_id}", response_model=Payment)
def read_payment(payment_id: int, db: Session = Depends(get_db)):
    """Retrieve a single payment by ID."""
    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return db_payment

@router.patch("/{payment_id}", response_model=Payment)
def update_payment(
    payment_id: int,
    payment_update: PaymentUpdate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Update an existing payment."""
    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    old_amount_paid = db_payment.amount_paid # Store old amount for PO total recalculation
    
    payment_data = payment_update.model_dump(exclude_unset=True)
    for key, value in payment_data.items():
        setattr(db_payment, key, value)
    
    db.commit()
    db.refresh(db_payment)

    # Re-evaluate PO payment status and total if amount changed
    db_po = db_payment.purchase_order # Access the related PO directly
    if db_po:
        updated_paid_amount = sum([p.amount_paid for p in db_po.payments])
        
        if updated_paid_amount >= db_po.total_amount:
            db_po.status = PurchaseOrderStatus.PAID
        elif updated_paid_amount > 0:
            db_po.status = PurchaseOrderStatus.PARTIALLY_PAID
        else: # updated_paid_amount is 0 or less (shouldn't be less)
            db_po.status = PurchaseOrderStatus.DRAFT # Or whatever initial status is if no payments

        db.commit() # Commit PO status update
        db.refresh(db_po) # Refresh PO to get updated status

    logger.info(f"Payment ID {payment_id} updated for Purchase Order ID {db_payment.purchase_order_id} by {x_user_id}")
    return db_payment

@router.delete("/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """Delete a payment."""
    db_payment = db.query(PaymentModel).filter(PaymentModel.id == payment_id).first()
    if db_payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")

    db_po = db_payment.purchase_order # Get the related PO
    
    db.delete(db_payment)
    db.commit()

    # Re-evaluate PO payment status after deletion
    if db_po:
        db.refresh(db_po) # Refresh PO to ensure payments relationship is updated
        updated_paid_amount = sum([p.amount_paid for p in db_po.payments])

        if updated_paid_amount >= db_po.total_amount:
            db_po.status = PurchaseOrderStatus.PAID
        elif updated_paid_amount > 0:
            db_po.status = PurchaseOrderStatus.PARTIALLY_PAID
        else: # No payments left
            db_po.status = PurchaseOrderStatus.APPROVED # Assuming PO is 'Approved' if no payments, but not 'Received'

        db.commit() # Commit PO status update

    logger.info(f"Payment ID {payment_id} deleted for Purchase Order ID {db_payment.purchase_order_id} by {x_user_id}")
    return {"message": "Payment deleted successfully"}