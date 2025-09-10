from sqlalchemy.orm import Session
from models.inventory_items import InventoryItem
from schemas.inventory_items import InventoryItemCreate, InventoryItemUpdate

def get_inventory_item(db: Session, item_id: int):
    return db.query(InventoryItem).filter(InventoryItem.id == item_id).first()

def get_inventory_items(db: Session, skip: int = 0, limit: int = 100):
    return db.query(InventoryItem).offset(skip).limit(limit).all()

def create_inventory_item(db: Session, item: InventoryItemCreate):
    db_item = InventoryItem(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_inventory_item(db: Session, item_id: int, item: InventoryItemUpdate):
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if db_item:
        update_data = item.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_item, key, value)
        db.commit()
        db.refresh(db_item)
    return db_item

def delete_inventory_item(db: Session, item_id: int):
    db_item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if db_item:
        db.delete(db_item)
        db.commit()
    return db_item
