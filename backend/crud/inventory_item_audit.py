from sqlalchemy.orm import Session
from models.inventory_item_audit import InventoryItemAudit
from typing import Optional
from datetime import date
from datetime import datetime
import pytz

def get_inventory_item_audits(
    db: Session, 
    inventory_item_id: int, 
    tenant_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    query = db.query(InventoryItemAudit).filter(
        InventoryItemAudit.inventory_item_id == inventory_item_id, 
        InventoryItemAudit.tenant_id == tenant_id
    )
    
    if start_date:
        query = query.filter(InventoryItemAudit.timestamp >= start_date)
    if end_date:
        query = query.filter(InventoryItemAudit.timestamp <= end_date)
        
    return query.all()


def create_inventory_item_audit(
    db: Session,
    inventory_item_id: int,
    change_type: str,
    change_amount: float,
    old_quantity: float,
    new_quantity: float,
    tenant_id: str,
    changed_by: Optional[str] = None,
    note: Optional[str] = None
):
    """Create an inventory item audit record."""
    audit = InventoryItemAudit(
        inventory_item_id=inventory_item_id,
        change_type=change_type,
        change_amount=change_amount,
        old_quantity=old_quantity,
        new_quantity=new_quantity,
        tenant_id=tenant_id,
        changed_by=changed_by,
        note=note,
        timestamp=datetime.now(pytz.timezone('Asia/Kolkata'))
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit