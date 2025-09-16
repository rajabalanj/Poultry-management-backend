from sqlalchemy.orm import Session
from models.composition_usage_history import CompositionUsageHistory
from models.composition import Composition
from models.inventory_item_in_composition import InventoryItemInComposition
from models.inventory_items import InventoryItem
from schemas.composition_usage_history import CompositionUsageHistoryCreate
from datetime import date, datetime
from decimal import Decimal
from models.inventory_item_audit import InventoryItemAudit
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


def use_composition(db: Session, composition_id: int, batch_id: int, times: int, used_at: datetime, tenant_id: str, changed_by: str = None):
    # Store usage history
    usage = CompositionUsageHistory(
        composition_id=composition_id,
        batch_id=batch_id,
        times=times,
        used_at=used_at,
        tenant_id=tenant_id
    )
    db.add(usage)

    batch_obj = db.query(Batch).filter(Batch.id == batch_id, Batch.tenant_id == tenant_id).first()
    shed_no = batch_obj.shed_no if batch_obj else "N/A"

    composition_obj = db.query(Composition).filter(Composition.id == composition_id, Composition.tenant_id == tenant_id).first()
    composition_name = composition_obj.name if composition_obj else "N/A"

    items_in_comp = db.query(InventoryItemInComposition).filter(InventoryItemInComposition.composition_id == composition_id, InventoryItemInComposition.tenant_id == tenant_id).all()

    for iic in items_in_comp:
        item = db.query(InventoryItem).filter(InventoryItem.id == iic.inventory_item_id, InventoryItem.tenant_id == tenant_id).first()
        if item:
            old_item_quantity = item.current_stock
            old_item_unit = item.unit

            old_quantity_for_audit_kg = _convert_quantity(old_item_quantity, old_item_unit, 'kg')

            total_iic_quantity_kg = Decimal(str(iic.weight)) * Decimal(str(times))
            
            try:
                quantity_to_reduce_in_items_unit = _convert_quantity(
                    total_iic_quantity_kg,
                    'kg',
                    old_item_unit
                )
            except ValueError as e:
                logger.error(f"Error converting IIC quantity for subtraction: {e}")
                raise

            item.current_stock -= quantity_to_reduce_in_items_unit
            db.add(item)
            db.flush()

            new_quantity_for_audit_kg = _convert_quantity(item.current_stock, item.unit, 'kg')

            change_amount_for_audit_kg = new_quantity_for_audit_kg - old_quantity_for_audit_kg

            audit = InventoryItemAudit(
                inventory_item_id=item.id,
                change_type="composition_usage",
                change_amount=change_amount_for_audit_kg,
                old_quantity=old_quantity_for_audit_kg,
                new_quantity=new_quantity_for_audit_kg,
                changed_by=changed_by,
                note=f"Used in composition '{composition_name}' for batch '{shed_no}' ({times} times).",
                tenant_id=tenant_id
            )
            db.add(audit)
    
    db.commit()
    db.refresh(usage)

    return usage

def create_composition_usage_history(db: Session, composition_id: int, times: int, used_at: datetime, tenant_id: str, batch_id: int = None):
    # import pdb; pdb.set_trace()
    usage = CompositionUsageHistory(
        composition_id=composition_id,
        times=times,
        used_at=used_at,
        batch_id=batch_id,
        tenant_id=tenant_id
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    return usage

def get_composition_usage_history(db: Session, tenant_id: str, composition_id: int = None):
    query = db.query(CompositionUsageHistory).filter(CompositionUsageHistory.tenant_id == tenant_id)
    if composition_id:
        query = query.filter(CompositionUsageHistory.composition_id == composition_id)
    usage_list = query.order_by(CompositionUsageHistory.used_at.desc()).all()

    result = []
    for usage in usage_list:
        composition = db.query(Composition).filter(Composition.id == usage.composition_id, Composition.tenant_id == tenant_id).first()
        usage_dict = usage.__dict__.copy()
        usage_dict.pop('_sa_instance_state', None) # Remove SQLAlchemy internal state

        usage_dict['composition_name'] = composition.name if composition else None

        # Safely fetch shed_no from Batch
        # Check if 'batch_id' exists in the usage record and if a Batch can be found
        # This part ensures graceful handling if batch_id is missing or Batch not found.
        if hasattr(usage, 'batch_id') and usage.batch_id is not None:
            batch = db.query(Batch).filter(Batch.id == usage.batch_id, Batch.tenant_id == tenant_id).first()
            if batch:
                usage_dict['shed_no'] = batch.shed_no
            else:
                usage_dict['shed_no'] = None # Set to None if batch not found for a given batch_id
        else:
            usage_dict['shed_no'] = None # Set to None if batch_id is missing from usage record

        result.append(usage_dict)
    return result

def revert_composition_usage(db: Session, usage_id: int, tenant_id: str, changed_by: str = None):
    """
    Reverts a specific composition usage, adding back item quantities and auditing the reversal.
    """
    usage_to_revert = db.query(CompositionUsageHistory).filter(CompositionUsageHistory.id == usage_id, CompositionUsageHistory.tenant_id == tenant_id).first()
    if not usage_to_revert:
        return False, "Composition usage record not found."

    composition_id = usage_to_revert.composition_id
    times = usage_to_revert.times

    composition_obj = db.query(Composition).filter(Composition.id == composition_id, Composition.tenant_id == tenant_id).first()
    composition_name = composition_obj.name if composition_obj else "N/A"

    batch_obj = db.query(Batch).filter(Batch.id == usage_to_revert.batch_id, Batch.tenant_id == tenant_id).first()
    shed_no = batch_obj.shed_no if batch_obj else "N/A"

    items_in_comp = db.query(InventoryItemInComposition).filter(InventoryItemInComposition.composition_id == composition_id, InventoryItemInComposition.tenant_id == tenant_id).all()

    for iic in items_in_comp:
        item = db.query(InventoryItem).filter(InventoryItem.id == iic.inventory_item_id, InventoryItem.tenant_id == tenant_id).first()
        if item:
            old_item_quantity = item.current_stock
            old_item_unit = item.unit

            old_quantity_for_audit_kg = _convert_quantity(old_item_quantity, old_item_unit, 'kg')

            total_iic_quantity_kg = Decimal(str(iic.weight)) * Decimal(str(times))

            try:
                quantity_to_add_in_items_unit = _convert_quantity(
                    total_iic_quantity_kg,
                    'kg',
                    old_item_unit
                )
            except ValueError as e:
                logger.error(f"Error converting IIC quantity for addition: {e}")
                raise

            item.current_stock += quantity_to_add_in_items_unit
            db.add(item)
            db.flush()

            new_quantity_for_audit_kg = _convert_quantity(item.current_stock, item.unit, 'kg')

            change_amount_for_audit_kg = new_quantity_for_audit_kg - old_quantity_for_audit_kg

            audit = InventoryItemAudit(
                inventory_item_id=item.id,
                change_type="composition_revert",
                change_amount=change_amount_for_audit_kg,
                old_quantity=old_quantity_for_audit_kg,
                new_quantity=new_quantity_for_audit_kg,
                changed_by=changed_by,
                note=f"Reverted usage of composition '{composition_name}' for batch '{shed_no}' ({times} times).",
                tenant_id=tenant_id
            )
            db.add(audit)

    db.delete(usage_to_revert)
    db.commit()
    return True, "Composition usage reverted successfully."

def get_composition_usage_by_date(db: Session, usage_date: date, tenant_id: str, batch_id: int = None):
    start_of_day = datetime.combine(usage_date, datetime.min.time())
    end_of_day = datetime.combine(usage_date, datetime.max.time())

    query = db.query(CompositionUsageHistory).filter(
        CompositionUsageHistory.used_at >= start_of_day,
        CompositionUsageHistory.used_at <= end_of_day,
        CompositionUsageHistory.tenant_id == tenant_id
    )

    if batch_id:
        query = query.filter(CompositionUsageHistory.batch_id == batch_id)

    usage_history = query.all()

    total_feed = 0
    feed_breakdown = {}

    for usage in usage_history:
        composition = usage.composition
        feed_quantity = 0
        for item_in_comp in composition.inventory_items:
            if item_in_comp.inventory_item and item_in_comp.inventory_item.category == 'Feed':
                feed_quantity += item_in_comp.weight * usage.times
        
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
