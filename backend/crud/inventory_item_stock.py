from sqlalchemy.orm import Session
from models.inventory_item_audit import InventoryItemAudit
from typing import Optional, List
from datetime import date, datetime, time, timedelta
import pytz
from decimal import Decimal

def get_stock_at_date(db: Session, inventory_item_id: int, tenant_id: str, target_date: date) -> Optional[Decimal]:
    """
    Get the stock of an inventory item at the end of a specific date.
    """
    end_of_day = datetime.combine(target_date, time.max, tzinfo=pytz.timezone('Asia/Kolkata'))

    last_audit = db.query(InventoryItemAudit).filter(
        InventoryItemAudit.inventory_item_id == inventory_item_id,
        InventoryItemAudit.tenant_id == tenant_id,
        InventoryItemAudit.timestamp <= end_of_day
    ).order_by(InventoryItemAudit.timestamp.desc()).first()

    if last_audit:
        return last_audit.new_quantity
    
    # If no audit trail is found before the target date, check for the first audit after
    first_audit_after = db.query(InventoryItemAudit).filter(
        InventoryItemAudit.inventory_item_id == inventory_item_id,
        InventoryItemAudit.tenant_id == tenant_id,
        InventoryItemAudit.timestamp > end_of_day
    ).order_by(InventoryItemAudit.timestamp.asc()).first()

    if first_audit_after:
        return first_audit_after.old_quantity

    return None

def get_daily_stock_report(db: Session, inventory_item_id: int, tenant_id: str, start_date: date, end_date: date) -> List[dict]:
    """
    Get the daily stock of an inventory item over a date range.
    """
    # This is a simplified and potentially slow implementation.
    # For production, you would want a more efficient way to do this,
    # possibly with a single more complex query.
    
    report = []
    current_date = start_date
    while current_date <= end_date:
        stock = get_stock_at_date(db, inventory_item_id, tenant_id, current_date)
        report.append({"date": current_date.isoformat(), "stock": stock})
        current_date += timedelta(days=1)
        
    return report

