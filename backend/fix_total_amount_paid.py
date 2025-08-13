#!/usr/bin/env python3
"""
Script to update existing purchase orders with correct total_amount_paid values
based on their existing payments.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
from models.purchase_orders import PurchaseOrder
from models.payments import Payment
from decimal import Decimal

def fix_total_amount_paid():
    """Update total_amount_paid for all existing purchase orders."""
    db: Session = SessionLocal()
    try:
        # Get all purchase orders
        purchase_orders = db.query(PurchaseOrder).all()
        
        updated_count = 0
        for po in purchase_orders:
            # Calculate total payments for this PO
            total_paid = db.query(Payment).filter(
                Payment.purchase_order_id == po.id
            ).with_entities(
                func.coalesce(func.sum(Payment.amount_paid), 0)
            ).scalar()
            
            # Update the total_amount_paid field
            po.total_amount_paid = Decimal(str(total_paid))
            updated_count += 1
            
            print(f"PO ID {po.id}: Updated total_amount_paid to {po.total_amount_paid}")
        
        db.commit()
        print(f"\nSuccessfully updated {updated_count} purchase orders.")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_total_amount_paid()