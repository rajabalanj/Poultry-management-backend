from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from database import get_db
import crud.feed as crud_feed # Assuming this is a feed-specific crud
import logging
from typing import List, Optional
from models.feed import Feed as FeedModel # Assuming FeedModel exists
from schemas.feed import Feed as FeedSchema # Assuming FeedSchema exists
from models.feed_audit import FeedAudit as FeedAuditModel # Assuming FeedAuditModel exists
from utils.auth_utils import get_current_user

# Assuming these imports exist and are correct for the feed module
# router = APIRouter(prefix="/feed", tags=["feed"])
# logger = logging.getLogger("feed")

# Re-using the router and logger from the original medicine.py for consistency in context
# In a real application, you'd likely have a separate router/logger for feed.
router = APIRouter(prefix="/feed", tags=["feed"])
logger = logging.getLogger("feed")

@router.get("/{feed_id}")
def get_feed(feed_id: int, db: Session = Depends(get_db)):
    """Get a specific feed by ID."""
    db_feed = crud_feed.get_feed(db, feed_id=feed_id)
    if db_feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    return db_feed

@router.get("/all/")
def get_all_feeds(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all feeds with pagination."""
    feeds = crud_feed.get_all_feeds(db, skip=skip, limit=limit)
    return feeds

@router.post("/")
def create_feed(
    feed: FeedSchema, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Create a new feed."""
    return crud_feed.create_feed(db=db, feed=feed, changed_by=user.get('sub'))

@router.patch("/{feed_id}")
def update_feed(
    feed_id: int, 
    feed_data: dict, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Update an existing feed."""
    db_feed = db.query(FeedModel).filter(FeedModel.id == feed_id).first() # Use FeedModel
    if not db_feed:
        return None

    old_quantity = db_feed.quantity
    old_unit = db_feed.unit # Get the current unit from the database record

    # Get the new quantity and unit from the incoming data, default to old values if not provided
    new_quantity = feed_data.get("quantity", old_quantity)
    new_unit = feed_data.get("unit", old_unit)

    # Convert old_quantity to kilograms for consistent calculation and storage
    old_quantity_kg = Decimal(str(old_quantity))
    if old_unit == 'ton':
        old_quantity_kg *= 1000 # 1 ton = 1000 kg

    # Convert new_quantity to kilograms for consistent calculation and storage
    new_quantity_decimal = Decimal(str(new_quantity))
    if new_unit == 'ton':
        new_quantity_decimal *= 1000 # 1 ton = 1000 kg

    change_amount_kg = Decimal('0')

    # Update the provided fields
    for key, value in feed_data.items():
        setattr(db_feed, key, value)
    
    db.commit()
    db.refresh(db_feed)

    # Audit only if quantity changed (comparison in kilograms)
    if old_quantity_kg != new_quantity_decimal:
        change_amount_kg = new_quantity_decimal - old_quantity_kg
        
        # Determine a simple note
        audit_note = "Manual edit: Feed quantity changed."

        audit = FeedAuditModel( # Use FeedAuditModel
            feed_id=feed_id,
            change_type="manual", # Assuming "manual" is a valid type for FeedAudit
            change_amount=change_amount_kg, # Store in kg
            old_weight=old_quantity_kg,     # Store in kg
            new_weight=new_quantity_decimal,   # Store in kg
            changed_by=user.get('sub'),
            note=audit_note, # Simple note
        )
        db.add(audit)
        db.commit()

    return db_feed

@router.delete("/{feed_id}")
def delete_feed(
    feed_id: int, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Delete a specific feed."""
    success = crud_feed.delete_feed(db, feed_id=feed_id, changed_by=user.get('sub'))
    if not success:
        raise HTTPException(status_code=404, detail="Feed not found")
    return {"message": "Feed deleted successfully"}

# Assuming the get_feed_audit for medicine was a copy-paste error in the previous turn,
# if there's a separate get_feed_audit for feed, it would look like this:
@router.get("/{feed_id}/audit/", response_model=List[dict])
def get_feed_audit(feed_id: int, db: Session = Depends(get_db)):
    audits = db.query(FeedAuditModel).filter(FeedAuditModel.feed_id == feed_id).order_by(FeedAuditModel.timestamp.desc()).all()
    return [
        {
            "timestamp": a.timestamp,
            "change_type": a.change_type,
            "change_amount": a.change_amount,
            "old_weight": a.old_weight,
            "new_weight": a.new_weight,
            "changed_by": a.changed_by,
            "note": a.note,
        }
        for a in audits
    ]