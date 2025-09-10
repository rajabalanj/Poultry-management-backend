from sqlalchemy.orm import Session
from models.inventory_item_audit import InventoryItemAudit

def get_inventory_item_audits(db: Session, inventory_item_id: int):
    return db.query(InventoryItemAudit).filter(InventoryItemAudit.inventory_item_id == inventory_item_id).all()
