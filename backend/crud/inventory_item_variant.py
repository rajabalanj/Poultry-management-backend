from sqlalchemy.orm import Session
from models.inventory_item_variant import InventoryItemVariant
from schemas.inventory_item_variant import InventoryItemVariantCreate

def create_inventory_item_variant(db: Session, variant: InventoryItemVariantCreate, tenant_id: str):
    db_variant = InventoryItemVariant(**variant.model_dump(), tenant_id=tenant_id)
    db.add(db_variant)
    db.commit()
    db.refresh(db_variant)
    return db_variant

def get_inventory_item_variants_by_item(db: Session, item_id: int, tenant_id: str):
    return db.query(InventoryItemVariant).filter(InventoryItemVariant.item_id == item_id, InventoryItemVariant.tenant_id == tenant_id).all()

def get_inventory_item_variant(db: Session, variant_id: int, tenant_id: str):
    return db.query(InventoryItemVariant).filter(InventoryItemVariant.id == variant_id, InventoryItemVariant.tenant_id == tenant_id).first()

def delete_inventory_item_variant(db: Session, variant_id: int, tenant_id: str):
    db_variant = get_inventory_item_variant(db, variant_id, tenant_id)
    if db_variant:
        db.delete(db_variant)
        db.commit()
    return db_variant
