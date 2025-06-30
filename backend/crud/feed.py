from sqlalchemy.orm import Session
from sqlalchemy import func
from models.feed import Feed
# from schemas.batch import BatchCreate
from datetime import date
from schemas.feed import Feed as FeedSchema

def get_feed(db: Session, feed_id: int):
    return db.query(Feed).filter(Feed.id == feed_id).first()

def get_all_feeds(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Feed).offset(skip).limit(limit).all()

def create_feed(db: Session, feed: Feed, changed_by: str = None):
    db_feed = Feed(
        title=feed.title,
        createdDate=feed.createdDate,
        quantity=feed.quantity,
        unit=feed.unit,
        warningKgThreshold=feed.warningKgThreshold,
        warningTonThreshold=feed.warningTonThreshold,
    )
    db.add(db_feed)
    db.commit()
    db.refresh(db_feed)
    return db_feed

def update_feed(db: Session, feed_id: int, feed_data: dict, changed_by: str = None):
    db_feed = db.query(Feed).filter(Feed.id == feed_id).first()
    if not db_feed:
        return None

    # Update the provided fields
    for key, value in feed_data.items():
        setattr(db_feed, key, value)
    
    db.commit()
    db.refresh(db_feed)
    return db_feed

def delete_feed(db: Session, feed_id: int, changed_by: str = None):
    db_feed = db.query(Feed).filter(Feed.id == feed_id).first()
    if not db_feed:
        return None

    db.delete(db_feed)
    db.commit()
    return db_feed