from sqlalchemy.orm import Session
from models.composition import Composition
from models.feed_in_composition import FeedInComposition
from schemas.compositon import CompositionCreate

def create_composition(db: Session, composition: CompositionCreate):
    db_composition = Composition(name=composition.name)
    db.add(db_composition)
    db.flush()
    for feed in composition.feeds:
        db_feed = FeedInComposition(
            composition_id=db_composition.id,
            feed_id=feed.feed_id,
            weight=feed.weight
        )
        db.add(db_feed)
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
    db.query(FeedInComposition).filter(FeedInComposition.composition_id == composition_id).delete()
    for feed in composition.feeds:
        db_feed = FeedInComposition(
            composition_id=composition_id,
            feed_id=feed.feed_id,
            weight=feed.weight
        )
        db.add(db_feed)
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