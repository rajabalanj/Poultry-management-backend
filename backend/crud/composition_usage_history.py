from sqlalchemy.orm import Session
from sqlalchemy import func
from models.composition_usage_history import CompositionUsageHistory
from models.composition import Composition
from models.inventory_item_in_composition import InventoryItemInComposition
from models.inventory_items import InventoryItem
from datetime import date, datetime
from decimal import Decimal
from models.inventory_item_audit import InventoryItemAudit
from models.batch import Batch
from models.composition_usage_item import CompositionUsageItem
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
    composition_obj = db.query(Composition).filter(Composition.id == composition_id, Composition.tenant_id == tenant_id).first()
    if not composition_obj:
        raise ValueError("Composition not found")

    usage = CompositionUsageHistory(
        composition_id=composition_id,
        composition_name=composition_obj.name,
        batch_id=batch_id,
        times=times,
        used_at=used_at,
        tenant_id=tenant_id
    )
    db.add(usage)
    db.flush() # Flush to get the usage id

    items_in_comp = db.query(InventoryItemInComposition).filter(InventoryItemInComposition.composition_id == composition_id, InventoryItemInComposition.tenant_id == tenant_id).all()
    
    for iic in items_in_comp:
        item = db.query(InventoryItem).filter(InventoryItem.id == iic.inventory_item_id, InventoryItem.tenant_id == tenant_id).first()
        if item:
            usage_item = CompositionUsageItem(
                usage_history_id=usage.id,
                inventory_item_id=iic.inventory_item_id,
                item_name=item.name,
                item_category=item.category,
                weight=iic.weight
            )
            usage.items.append(usage_item)

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

            batch_obj = db.query(Batch).filter(Batch.id == batch_id, Batch.tenant_id == tenant_id).first()
            batch_no = batch_obj.batch_no if batch_obj else None

            audit = InventoryItemAudit(
                inventory_item_id=item.id,
                change_type="composition_usage",
                change_amount=change_amount_for_audit_kg,
                old_quantity=old_quantity_for_audit_kg,
                new_quantity=new_quantity_for_audit_kg,
                changed_by=changed_by,
                note=f"Used in composition '{composition_obj.name}' for batch '{batch_no}' ({times} times).",
                tenant_id=tenant_id
            )
            db.add(audit)
    
    db.commit()
    db.refresh(usage)

    return usage

def create_composition_usage_history(db: Session, composition_id: int, times: int, used_at: datetime, tenant_id: str, batch_id: int = None):
    composition_obj = db.query(Composition).filter(Composition.id == composition_id, Composition.tenant_id == tenant_id).first()
    if not composition_obj:
        raise ValueError("Composition not found")

    usage = CompositionUsageHistory(
        composition_id=composition_id,
        composition_name=composition_obj.name,
        times=times,
        used_at=used_at,
        batch_id=batch_id,
        tenant_id=tenant_id
    )
    db.add(usage)
    db.flush() # Flush to get usage.id

    items_in_comp = db.query(InventoryItemInComposition).filter(InventoryItemInComposition.composition_id == composition_id, InventoryItemInComposition.tenant_id == tenant_id).all()
    for iic in items_in_comp:
        item = db.query(InventoryItem).filter(InventoryItem.id == iic.inventory_item_id, InventoryItem.tenant_id == tenant_id).first()
        if item:
            usage_item = CompositionUsageItem(
                usage_history_id=usage.id,
                inventory_item_id=iic.inventory_item_id,
                item_name=item.name,
                item_category=item.category,
                weight=iic.weight
            )
            db.add(usage_item)

    db.commit()
    db.refresh(usage)
    return usage

def get_composition_usage_history(db: Session, tenant_id: str, composition_id: int = None, offset: int = 0, limit: int = 10, start_date: date = None, end_date: date = None):
    query = db.query(CompositionUsageHistory).filter(CompositionUsageHistory.tenant_id == tenant_id)
    if composition_id:
        query = query.filter(CompositionUsageHistory.composition_id == composition_id)
    
    # Apply date range filter if provided
    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        query = query.filter(CompositionUsageHistory.used_at >= start_datetime)
    
    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(CompositionUsageHistory.used_at <= end_datetime)
    
    total = query.count()
    results = query.order_by(CompositionUsageHistory.used_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "data": results,
        "total": total
    }

def revert_composition_usage(db: Session, usage_id: int, tenant_id: str, changed_by: str = None):
    """
    Reverts a specific composition usage, adding back item quantities and auditing the reversal.
    """
    usage_to_revert = db.query(CompositionUsageHistory).filter(CompositionUsageHistory.id == usage_id, CompositionUsageHistory.tenant_id == tenant_id).first()
    if not usage_to_revert:
        return False, "Composition usage record not found."

    times = usage_to_revert.times
    composition_name = usage_to_revert.composition_name
    
    batch_obj = db.query(Batch).filter(Batch.id == usage_to_revert.batch_id, Batch.tenant_id == tenant_id).first()
    batch_no = batch_obj.batch_no if batch_obj else None

    for usage_item in usage_to_revert.items:
        item = db.query(InventoryItem).filter(InventoryItem.id == usage_item.inventory_item_id, InventoryItem.tenant_id == tenant_id).first()
        if item:
            old_item_quantity = item.current_stock
            old_item_unit = item.unit

            old_quantity_for_audit_kg = _convert_quantity(old_item_quantity, old_item_unit, 'kg')

            total_iic_quantity_kg = Decimal(usage_item.weight) * Decimal(times)

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

            new_quantity_for_audit_kg = _convert_quantity(item.current_stock, item.unit, 'kg')

            change_amount_for_audit_kg = new_quantity_for_audit_kg - old_quantity_for_audit_kg

            audit = InventoryItemAudit(
                inventory_item_id=item.id,
                change_type="composition_revert",
                change_amount=change_amount_for_audit_kg,
                old_quantity=old_quantity_for_audit_kg,
                new_quantity=new_quantity_for_audit_kg,
                changed_by=changed_by,
                note=f"Reverted usage of composition '{composition_name}' for batch '{batch_no}' ({times} times).",
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
        feed_quantity = 0
        for usage_item in usage.items:
            if usage_item.item_category == 'Feed':
                feed_quantity += Decimal(usage_item.weight) * usage.times
        
        total_feed += feed_quantity
        composition_name = usage.composition_name
        if composition_name in feed_breakdown:
            feed_breakdown[composition_name] += feed_quantity
        else:
            feed_breakdown[composition_name] = feed_quantity

    feed_breakdown_list = [{"feed_type": f, "amount": a} for f, a in feed_breakdown.items()]

    return {
        "total_feed": total_feed,
        "feed_breakdown": feed_breakdown_list
    }


def get_composition_usage_by_date_range(db: Session, start_date: date, end_date: date, tenant_id: str):
    """
    Calculates the total usage of each composition within a given date range.
    """
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Subquery to get the total weight of each composition usage
    subquery = db.query(
        CompositionUsageHistory.id.label("usage_id"),
        (func.sum(CompositionUsageItem.weight) * CompositionUsageHistory.times).label("total_weight")
    ).join(
        CompositionUsageItem, CompositionUsageHistory.id == CompositionUsageItem.usage_history_id
    ).filter(
        CompositionUsageHistory.tenant_id == tenant_id,
        CompositionUsageHistory.used_at >= start_datetime,
        CompositionUsageHistory.used_at <= end_datetime
    ).group_by(
        CompositionUsageHistory.id
    ).subquery()

    # Main query to sum up the total weights by composition name
    results = db.query(
        CompositionUsageHistory.composition_name,
        func.sum(subquery.c.total_weight).label('total_usage')
    ).join(
        subquery, CompositionUsageHistory.id == subquery.c.usage_id
    ).group_by(
        CompositionUsageHistory.composition_name
    ).all()

    return [{"composition_name": name, "total_usage": total_usage, "unit": "kg"} for name, total_usage in results]
