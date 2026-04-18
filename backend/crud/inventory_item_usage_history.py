from sqlalchemy.orm import Session
from sqlalchemy import func
from models.inventory_item_usage_history import InventoryItemUsageHistory
from models.inventory_items import InventoryItem
from models.inventory_item_audit import InventoryItemAudit
from models.batch import Batch
from datetime import date, datetime
import pytz
from decimal import Decimal
import logging
from crud.composition_usage_history import _convert_quantity

logger = logging.getLogger(__name__)


def use_inventory_item(
    db: Session,
    inventory_item_id: int,
    batch_id: int,
    used_quantity: Decimal,
    used_at: datetime,
    tenant_id: str,
    changed_by: str = None,
    unit: str = None
):
    item = db.query(InventoryItem).filter(
        InventoryItem.id == inventory_item_id,
        InventoryItem.tenant_id == tenant_id
    ).first()
    if not item:
        raise ValueError("Inventory item not found")

    if used_quantity <= 0:
        raise ValueError("Used quantity must be greater than zero")
    
    if unit and unit != item.unit:
        try:
            used_quantity = _convert_quantity(used_quantity, unit, item.unit)
        except ValueError as e:
            raise ValueError(f"Unit conversion failed: {str(e)}")
        
    current_stock = item.current_stock or Decimal('0')
    if current_stock < used_quantity:
        raise ValueError("Insufficient stock for inventory item usage")

    usage = InventoryItemUsageHistory(
        inventory_item_id=inventory_item_id,
        used_quantity=used_quantity,
        unit=item.unit,
        used_at=used_at,
        batch_id=batch_id,
        changed_by=changed_by,
        tenant_id=tenant_id
    )
    db.add(usage)

    old_quantity = current_stock
    item.current_stock = current_stock - used_quantity
    db.add(item)

    audit = InventoryItemAudit(
        inventory_item_id=item.id,
        change_type="inventory_usage",
        change_amount=-used_quantity,
        old_quantity=old_quantity,
        new_quantity=item.current_stock,
        changed_by=changed_by,
        note=f"Direct inventory item usage for batch ID {batch_id}",
        tenant_id=tenant_id,
        timestamp=datetime.now(pytz.timezone('Asia/Kolkata'))
    )
    db.add(audit)

    db.commit()
    db.refresh(usage)

    # --- Create Journal Entry for COGS (Cost of Goods Sold) ---
    try:
        from crud.financial_settings import get_financial_settings
        from crud import journal_entry as journal_entry_crud
        from schemas.journal_entry import JournalEntryCreate
        from schemas.journal_item import JournalItemCreate
        import logging

        logger = logging.getLogger(__name__)

        # 1. Get Accounts
        settings = get_financial_settings(db, tenant_id)

        if not settings.default_cogs_account_id or not settings.default_inventory_account_id:
            logger.error(f"Default COGS or Inventory account not configured in Financial Settings for tenant {tenant_id}. Journal entry skipped.")
        else:
            # 2. Calculate Total Cost
            # The used_quantity is already in the item's unit (after conversion if needed)
            total_cost = used_quantity * (item.average_cost or Decimal('0'))

            if total_cost > 0:
                # Round total_cost to 2 decimal places to match journal entry requirements
                total_cost = total_cost.quantize(Decimal('0.01'))

                # 3. Create Journal Entry
                # Debit COGS (Expense), Credit Inventory (Asset)
                journal_items = [
                    JournalItemCreate(
                        account_id=settings.default_cogs_account_id,
                        debit=total_cost,
                        credit=Decimal('0.0')
                    ),
                    JournalItemCreate(
                        account_id=settings.default_inventory_account_id,
                        debit=Decimal('0.0'),
                        credit=total_cost
                    )
                ]

                journal_entry = JournalEntryCreate(
                    date=used_at.date() if isinstance(used_at, datetime) else used_at,
                    description=f"COGS for Direct Inventory Usage #{usage.id} ({item.name})",
                    reference_document=f"INV-USAGE-{usage.id}",
                    items=journal_items
                )
                journal_entry_crud.create_journal_entry(db=db, entry=journal_entry, tenant_id=tenant_id)
                logger.info(f"Created COGS Journal Entry for Inventory Usage {usage.id}: {total_cost}")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create COGS journal entry for inventory usage {usage.id}: {e}")
    # --- End Journal Entry ---

    return usage


def get_inventory_item_usage_history(
    db: Session,
    tenant_id: str,
    inventory_item_id: int = None,
    offset: int = 0,
    limit: int = 10,
    start_date: date = None,
    end_date: date = None
):
    query = db.query(InventoryItemUsageHistory).filter(InventoryItemUsageHistory.tenant_id == tenant_id)
    if inventory_item_id:
        query = query.filter(InventoryItemUsageHistory.inventory_item_id == inventory_item_id)

    if start_date:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        query = query.filter(InventoryItemUsageHistory.used_at >= start_datetime)

    if end_date:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(InventoryItemUsageHistory.used_at <= end_datetime)

    total = query.count()
    results = query.order_by(InventoryItemUsageHistory.used_at.desc()).offset(offset).limit(limit).all()
    return {
        "data": results,
        "total": total
    }


def get_inventory_item_usage_by_date(
    db: Session,
    usage_date: date,
    tenant_id: str,
    batch_id: int = None
):
    start_of_day = datetime.combine(usage_date, datetime.min.time())
    end_of_day = datetime.combine(usage_date, datetime.max.time())

    query = db.query(InventoryItemUsageHistory).filter(
        InventoryItemUsageHistory.tenant_id == tenant_id,
        InventoryItemUsageHistory.used_at >= start_of_day,
        InventoryItemUsageHistory.used_at <= end_of_day
    )

    if batch_id:
        query = query.filter(InventoryItemUsageHistory.batch_id == batch_id)

    usage_history = query.all()

    # Fetch all inventory items for the tenant to get their names
    inventory_items = db.query(InventoryItem).filter(
        InventoryItem.tenant_id == tenant_id
    ).all()

    # Create a mapping of inventory_item_id to name
    item_name_map = {item.id: item.name for item in inventory_items}

    total_used = Decimal('0')
    breakdown = {}

    for usage in usage_history:
        total_used += usage.used_quantity
        key = (usage.inventory_item_id, usage.unit)
        breakdown[key] = breakdown.get(key, Decimal('0')) + usage.used_quantity

    breakdown_list = [
        {
            "inventory_item_id": item_id,
            "name": item_name_map.get(item_id, "Unknown"),
            "amount": amount,
            "unit": unit
        }
        for (item_id, unit), amount in breakdown.items()
    ]

    return {
        "total_used": total_used,
        "breakdown": breakdown_list
    }


def revert_inventory_item_usage(db: Session, usage_id: int, tenant_id: str, changed_by: str = None):
    usage = db.query(InventoryItemUsageHistory).filter(
        InventoryItemUsageHistory.id == usage_id,
        InventoryItemUsageHistory.tenant_id == tenant_id
    ).first()
    if not usage:
        return False, "Inventory item usage record not found."

    item = db.query(InventoryItem).filter(
        InventoryItem.id == usage.inventory_item_id,
        InventoryItem.tenant_id == tenant_id
    ).first()
    if not item:
        return False, "Inventory item not found for usage revert."

    old_quantity = item.current_stock or Decimal('0')
    item.current_stock = old_quantity + usage.used_quantity
    db.add(item)

    audit = InventoryItemAudit(
        inventory_item_id=item.id,
        change_type="inventory_usage_revert",
        change_amount=usage.used_quantity,
        old_quantity=old_quantity,
        new_quantity=item.current_stock,
        changed_by=changed_by,
        note=f"Reverted direct inventory usage ID {usage.id}",
        tenant_id=tenant_id,
        timestamp=datetime.now(pytz.timezone('Asia/Kolkata'))
    )
    db.add(audit)

    db.delete(usage)
    db.commit()
    return True, "Inventory item usage reverted successfully."
