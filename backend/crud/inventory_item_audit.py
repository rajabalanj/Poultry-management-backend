from sqlalchemy.orm import Session
from models.inventory_item_audit import InventoryItemAudit
from typing import Optional
from datetime import date

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