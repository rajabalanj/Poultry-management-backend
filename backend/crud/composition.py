from sqlalchemy.orm import Session
from models.composition import Composition
from models.inventory_item_in_composition import InventoryItemInComposition
from schemas.composition import CompositionCreate

def create_composition(db: Session, composition: CompositionCreate):
    db_composition = Composition(name=composition.name)
    db.add(db_composition)
    db.flush()
    for item in composition.inventory_items:
        db_item = InventoryItemInComposition(
            composition_id=db_composition.id,
            inventory_item_id=item.inventory_item_id,
            weight=item.weight
        )
        db.add(db_item)
    db.commit()
    db.refresh(db_composition)
    return db_composition

def get_composition(db: Session, composition_id: int):
    return db.query(Composition).filter(Composition.id == composition_id).first()

def get_compositions(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Composition).offset(skip).limit(limit).all()

def update_composition(db: Session, composition_id: int, composition: CompositionCreate):
    db_composition = db.query(Composition).filter(Composition.id == composition_id).first()
    if not db_composition:
        return None
    db_composition.name = composition.name
    db.query(InventoryItemInComposition).filter(InventoryItemInComposition.composition_id == composition_id).delete()
    for item in composition.inventory_items:
        db_item = InventoryItemInComposition(
            composition_id=composition_id,
            inventory_item_id=item.inventory_item_id,
            weight=item.weight
        )
        db.add(db_item)
    db.commit()
    db.refresh(db_composition)
    return db_composition

def delete_composition(db: Session, composition_id: int):
    db_composition = db.query(Composition).filter(Composition.id == composition_id).first()
    if not db_composition:
        return False
    db.delete(db_composition)
    db.commit()
    return True
