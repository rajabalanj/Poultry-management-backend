from sqlalchemy.orm import Session
from models.composition_usage_history import CompositionUsageHistory
from models.composition import Composition
from models.feed_in_composition import FeedInComposition
from models.feed import Feed
from schemas.composition_usage_history import CompositionUsageHistoryCreate
from datetime import date, datetime
from decimal import Decimal
from models.feed_audit import FeedAudit
from models.batch import Batch
import logging

logger = logging.getLogger(__name__)

def _convert_quantity(quantity: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """
    Helper function to convert a quantity from one unit to another.
    Supported units: 'kg', 'ton', 'gram'.
    """
    if from_unit == to_unit:
        return quantity

    # Convert source unit to a common base (grams) first for intermediate calculation
    quantity_in_grams = quantity
    if from_unit == 'kg':
        quantity_in_grams *= 1000
    elif from_unit == 'ton':
        quantity_in_grams *= 1000000  # 1 ton = 1000 kg = 1,000,000 grams
    elif from_unit == 'gram':
        pass  # Already in grams
    else:
        raise ValueError(f"Unsupported 'from' unit for conversion: {from_unit}")

    # Convert from grams to target unit
    if to_unit == 'kg':
        return quantity_in_grams / 1000
    elif to_unit == 'ton':
        return quantity_in_grams / 1000000
    elif to_unit == 'gram':
        return quantity_in_grams
    else:
        raise ValueError(f"Unsupported 'to' unit for conversion: {to_unit}")


def use_composition(db: Session, composition_id: int, batch_id: int, times: int, used_at: datetime, changed_by: str = None):
    # Store usage history
    usage = CompositionUsageHistory(
        composition_id=composition_id,
        batch_id=batch_id,
        times=times,
        used_at=used_at
    )
    db.add(usage) # Add the usage object to the session here

    # Get the shed_no from the Batch model for the note
    batch_obj = db.query(Batch).filter(Batch.id == batch_id).first()
    shed_no = batch_obj.shed_no if batch_obj else "N/A"

    # Get composition name for the note
    composition_obj = db.query(Composition).filter(Composition.id == composition_id).first()
    composition_name = composition_obj.name if composition_obj else "N/A"

    # Get all feeds in the composition
    feeds_in_comp = db.query(FeedInComposition).filter(FeedInComposition.composition_id == composition_id).all()

    for fic in feeds_in_comp:
        feed = db.query(Feed).filter(Feed.id == fic.feed_id).first()
        if feed:
            old_feed_quantity = feed.quantity  # Quantity in its current unit (kg/ton/gram)
            old_feed_unit = feed.unit

            # Convert old quantity to KILOGRAMS for auditing
            old_quantity_for_audit_kg = _convert_quantity(old_feed_quantity, old_feed_unit, 'kg')

            # Calculate the total quantity to reduce from FeedInComposition
            # fic.quantity is always in 'kg' as per your clarification.
            total_fic_quantity_kg = Decimal(str(fic.weight)) * Decimal(str(times))
            
            # Convert total_fic_quantity_kg to the feed's *current* unit for accurate subtraction from feed.quantity
            try:
                quantity_to_reduce_in_feeds_unit = _convert_quantity(
                    total_fic_quantity_kg,
                    'kg', # Source unit is always 'kg' as per user clarification
                    old_feed_unit
                )
            except ValueError as e:
                logger.error(f"Error converting FIC quantity for subtraction: {e}")
                raise # Re-raise to indicate a critical conversion error

            # Update the feed's quantity in the database (in its original unit)
            feed.quantity -= quantity_to_reduce_in_feeds_unit
            db.add(feed) # Mark the feed object as modified for the session
            db.flush() # Flush to ensure feed.quantity is updated in the session before next read

            # Recalculate the new quantity in KILOGRAMS for auditing after the update
            new_quantity_for_audit_kg = _convert_quantity(feed.quantity, feed.unit, 'kg')

            # Calculate change amount for audit in KILOGRAMS
            change_amount_for_audit_kg = new_quantity_for_audit_kg - old_quantity_for_audit_kg

            # Create FeedAudit record
            audit = FeedAudit(
                feed_id=feed.id,
                change_type="composition_usage",
                change_amount=change_amount_for_audit_kg, # Store in kilograms
                old_weight=old_quantity_for_audit_kg,     # Store in kilograms
                new_weight=new_quantity_for_audit_kg,   # Store in kilograms
                changed_by=changed_by,
                note=f"Used in composition '{composition_name}' for batch '{shed_no}' ({times} times)."
            )
            db.add(audit)
    
    db.commit() # Commit all changes (usage history, feed updates, and audit records)
    db.refresh(usage) # <--- IMPORTANT: Refresh 'usage' to load its ID from the database

    return usage # <--- IMPORTANT: Return the 'usage' object

def create_composition_usage_history(db: Session, composition_id: int, times: int, used_at: datetime, batch_id: int = None):
    # import pdb; pdb.set_trace()
    usage = CompositionUsageHistory(
        composition_id=composition_id,
        times=times,
        used_at=used_at,
        batch_id=batch_id
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

    result = []
    for usage in usage_list:
        composition = db.query(Composition).filter(Composition.id == usage.composition_id).first()
        usage_dict = usage.__dict__.copy()
        usage_dict.pop('_sa_instance_state', None) # Remove SQLAlchemy internal state

        usage_dict['composition_name'] = composition.name if composition else None

        # Safely fetch shed_no from Batch
        # Check if 'batch_id' exists in the usage record and if a Batch can be found
        # This part ensures graceful handling if batch_id is missing or Batch not found.
        if hasattr(usage, 'batch_id') and usage.batch_id is not None:
            batch = db.query(Batch).filter(Batch.id == usage.batch_id).first()
            if batch:
                usage_dict['shed_no'] = batch.shed_no
            else:
                usage_dict['shed_no'] = None # Set to None if batch not found for a given batch_id
        else:
            usage_dict['shed_no'] = None # Set to None if batch_id is missing from usage record

        result.append(usage_dict)
    return result


def revert_composition_usage(db: Session, usage_id: int, changed_by: str = None):
    """
    Reverts a specific composition usage, adding back feed quantities and auditing the reversal.
    """
    usage_to_revert = db.query(CompositionUsageHistory).filter(CompositionUsageHistory.id == usage_id).first()
    if not usage_to_revert:
        return False, "Composition usage record not found."

    composition_id = usage_to_revert.composition_id
    times = usage_to_revert.times

    # Get composition name and batch shed_no for the audit note
    composition_obj = db.query(Composition).filter(Composition.id == composition_id).first()
    composition_name = composition_obj.name if composition_obj else "N/A"

    batch_obj = db.query(Batch).filter(Batch.id == usage_to_revert.batch_id).first()
    shed_no = batch_obj.shed_no if batch_obj else "N/A"

    feeds_in_comp = db.query(FeedInComposition).filter(FeedInComposition.composition_id == composition_id).all()

    for fic in feeds_in_comp:
        feed = db.query(Feed).filter(Feed.id == fic.feed_id).first()
        if feed:
            old_feed_quantity = feed.quantity
            old_feed_unit = feed.unit

            # Convert old quantity to KILOGRAMS for auditing
            old_quantity_for_audit_kg = _convert_quantity(old_feed_quantity, old_feed_unit, 'kg')

            # Calculate the total quantity to add back (always in kg from fic.weight)
            total_fic_quantity_kg = Decimal(str(fic.weight)) * Decimal(str(times))

            # Convert quantity to add back to the feed's *current* unit
            try:
                quantity_to_add_in_feeds_unit = _convert_quantity(
                    total_fic_quantity_kg,
                    'kg', # Source unit is always 'kg'
                    old_feed_unit
                )
            except ValueError as e:
                logger.error(f"Error converting FIC quantity for addition: {e}")
                raise

            # Add back the quantity to the feed
            feed.quantity += quantity_to_add_in_feeds_unit
            db.add(feed)
            db.flush() # Flush to ensure feed.quantity is updated before next read

            # Recalculate new quantity in KILOGRAMS for auditing
            new_quantity_for_audit_kg = _convert_quantity(feed.quantity, feed.unit, 'kg')

            # Calculate change amount for audit (positive as we are adding back)
            change_amount_for_audit_kg = new_quantity_for_audit_kg - old_quantity_for_audit_kg

            # Create FeedAudit record for the reversal
            audit = FeedAudit(
                feed_id=feed.id,
                change_type="composition_revert",
                change_amount=change_amount_for_audit_kg, # Store in kilograms
                old_weight=old_quantity_for_audit_kg,     # Store in kilograms
                new_weight=new_quantity_for_audit_kg,   # Store in kilograms
                changed_by=changed_by,
                note=f"Reverted usage of composition '{composition_name}' for batch '{shed_no}' ({times} times)."
            )
            db.add(audit)

    # Delete the original usage history record after successful reversal of quantities
    db.delete(usage_to_revert)
    db.commit()
    return True, "Composition usage reverted successfully."

def get_composition_usage_by_date(db: Session, usage_date: date, batch_id: int = None):
    start_of_day = datetime.combine(usage_date, datetime.min.time())
    end_of_day = datetime.combine(usage_date, datetime.max.time())

    query = db.query(CompositionUsageHistory).filter(
        CompositionUsageHistory.used_at >= start_of_day,
        CompositionUsageHistory.used_at <= end_of_day
    )

    if batch_id:
        query = query.filter(CompositionUsageHistory.batch_id == batch_id)

    usage_history = query.all()

    total_feed = 0
    feed_breakdown = {}

    for usage in usage_history:
        composition = usage.composition
        feed_quantity = 0
        for feed_in_comp in composition.feeds:
            feed_quantity += feed_in_comp.weight * usage.times
        
        total_feed += feed_quantity
        composition_name = composition.name
        if composition_name in feed_breakdown:
            feed_breakdown[composition_name] += feed_quantity
        else:
            feed_breakdown[composition_name] = feed_quantity

    feed_breakdown_list = [{"feed_type": f, "amount": a} for f, a in feed_breakdown.items()]

    return {
        "total_feed": total_feed,
        "feed_breakdown": feed_breakdown_list
    }

