from sqlalchemy.orm import Session
from models.composition_usage_history import CompositionUsageHistory
from models.composition import Composition
from models.feed_in_composition import FeedInComposition
from models.feed import Feed
from schemas.composition_usage_history import CompositionUsageHistoryCreate
from datetime import datetime
from decimal import Decimal
from models.feed_audit import FeedAudit

def use_composition(db: Session, composition_id: int, times: int, used_at: datetime):
    # Store usage history
    usage = CompositionUsageHistory(
        composition_id=composition_id,
        times=times,
        used_at=used_at
    )
    db.add(usage)
    # Get all feeds in the composition
    feeds_in_comp = db.query(FeedInComposition).filter(FeedInComposition.composition_id == composition_id).all()
    for fic in feeds_in_comp:
        feed = db.query(Feed).filter(Feed.id == fic.feed_id).first()
        if feed:
            if feed.unit == 'kg':
                # If feed is in kg, calculate the quantity to reduce
                # feed.quantity = feed.quantity - (Decimal(str(fic.weight)) * Decimal(str(times)))
                change_amount = -(Decimal(str(fic.weight)) * Decimal(str(times)))
                new_weight = feed.quantity - change_amount
            elif feed.unit == 'ton':
                # If feed is in tons, calculate the quantity to reduce
                # feed.quantity = feed.quantity - (Decimal(str(fic.weight)) * Decimal(str(times)) / Decimal('1000'))  # Convert tons to kg
                change_amount = -(Decimal(str(fic.weight)) * Decimal(str(times)) / Decimal('1000'))  # Convert tons to kg
                new_weight = feed.quantity - change_amount
            # Update the feed quantity
            feed.quantity = new_weight
            # Create a feed audit entry
            feed_audit = FeedAudit(
                feed_id=feed.id,
                change_type="composition",
                change_amount=-change_amount,
                old_weight=feed.quantity,
                new_weight=new_weight,
                timestamp=used_at,
                changed_by='system',  # Assuming system usage, can be modified to include user info
                note=f"Used in composition {composition_id} at {used_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            db.add(feed_audit)
         
    db.commit()
    db.refresh(usage)
    return usage

def create_composition_usage_history(db: Session, composition_id: int, times: int, used_at):
    usage = CompositionUsageHistory(
        composition_id=composition_id,
        times=times,
        used_at=used_at
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage


def get_composition_usage_history(db: Session, composition_id: int = None):
    query = db.query(CompositionUsageHistory)
    if composition_id:
        query = query.filter(CompositionUsageHistory.composition_id == composition_id)
    usage_list = query.order_by(CompositionUsageHistory.used_at.desc()).all()
    # Attach composition name to each usage record
    result = []
    for usage in usage_list:
        composition = db.query(Composition).filter(Composition.id == usage.composition_id).first()
        usage_dict = usage.__dict__.copy()
        usage_dict['composition_name'] = composition.name if composition else None
        usage_dict.pop('_sa_instance_state', None)
        result.append(usage_dict)
    return result
