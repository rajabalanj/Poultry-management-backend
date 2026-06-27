# Standard library imports
from datetime import datetime, date
from typing import Optional
import logging
from decimal import Decimal

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# Local application imports
from crud.composition_usage_history import use_composition, get_composition_usage_history, revert_composition_usage, get_composition_usage_by_date
from crud.financial_settings import get_financial_settings
from crud import journal_entry as journal_entry_crud
from database import get_db
from models.batch import Batch as BatchModel
from models.composition_usage_history import CompositionUsageHistory as CompositionUsageHistoryModel
from models.inventory_items import InventoryItem
from schemas.composition_usage_history import CompositionUsageHistory, CompositionUsageByDate, CompositionUsageCreate, PaginatedCompositionUsageHistoryResponse
from schemas.journal_entry import JournalEntryCreate
from schemas.journal_item import JournalItemCreate
from utils.auth_utils import get_current_user, get_user_identifier
from utils.tenancy import get_tenant_id

router = APIRouter(
    prefix="/compositions",
    tags=["Composition Usage History"],
)

logger = logging.getLogger(__name__)

@router.post("/use-composition")
def use_composition_endpoint(
    data: CompositionUsageCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    used_at_dt = data.usedAt or datetime.now()

    # Find the batch_id based on batch_no
    batch = db.query(BatchModel).filter(BatchModel.batch_no == data.batch_no, BatchModel.is_active, BatchModel.tenant_id == tenant_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Active batch with batch number '{data.batch_no}' not found.")
    batch_id = batch.id

    try:
        # Extract usage-time wastage percentage if provided
        usage_wastage = getattr(data, 'wastage_percentage', None)
        # Call use_composition and pass changed_by (user from token) and optional wastage
        usage = use_composition(
            db, 
            data.compositionId, 
            batch_id, 
            data.times, 
            used_at_dt, 
            changed_by=get_user_identifier(user), 
            tenant_id=tenant_id,
            wastage_percentage=usage_wastage
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Now, 'usage' object should have its ID populated
    if usage and hasattr(usage, 'id'):
        # --- Create Journal Entry for COGS (Cost of Goods Sold) ---
        try:
            # 1. Get Accounts
            settings = get_financial_settings(db, tenant_id)
            
            if not settings.default_cogs_account_id or not settings.default_inventory_account_id:
                logger.error(f"Default COGS or Inventory account not configured in Financial Settings for tenant {tenant_id}. Journal entry skipped.")
            else:
                # 2. Calculate Total Cost
                total_cost = Decimal(0)
                for usage_item in usage.items:
                    inv_item = db.query(InventoryItem).filter(InventoryItem.id == usage_item.inventory_item_id).first()
                    if inv_item:
                        # Calculate cost: weight * times * average_cost
                        base_quantity = Decimal(usage_item.weight) * Decimal(usage.times)
                        
                        # Deduct exact cost of gross inventory pulled
                        cost = base_quantity * (inv_item.average_cost or Decimal(0))
                        total_cost += cost
                
                if total_cost > 0:
                    rounded_actual = total_cost.quantize(Decimal('0.01'))
                    actual_times = Decimal(str(usage.times))

                    # 3. Create Journal Entry items list
                    journal_items = []

                    # If feed variance account is set and times is not exactly 1.0, split the cost
                    if settings.default_feed_variance_account_id and actual_times != Decimal('1.0') and actual_times > 0:
                        standard_cost = total_cost / actual_times
                        rounded_standard = standard_cost.quantize(Decimal('0.01'))
                        rounded_variance = rounded_actual - rounded_standard

                        # Standard cost goes to COGS
                        journal_items.append(
                            JournalItemCreate(
                                account_id=settings.default_cogs_account_id,
                                debit=rounded_standard,
                                credit=Decimal('0.0')
                            )
                        )

                        # Variance goes to Feed Variance account
                        if rounded_variance > 0:
                            # Excess: Debit Feed Variance
                            journal_items.append(
                                JournalItemCreate(
                                    account_id=settings.default_feed_variance_account_id,
                                    debit=rounded_variance,
                                    credit=Decimal('0.0')
                                )
                            )
                        elif rounded_variance < 0:
                            # Deficit: Credit Feed Variance
                            journal_items.append(
                                JournalItemCreate(
                                    account_id=settings.default_feed_variance_account_id,
                                    debit=Decimal('0.0'),
                                    credit=abs(rounded_variance)
                                )
                            )
                    else:
                        # Fallback: post the entire actual cost to COGS
                        journal_items.append(
                            JournalItemCreate(
                                account_id=settings.default_cogs_account_id,
                                debit=rounded_actual,
                                credit=Decimal('0.0')
                            )
                        )

                    # Credit Inventory (Asset) for the actual cost
                    journal_items.append(
                        JournalItemCreate(
                            account_id=settings.default_inventory_account_id,
                            debit=Decimal('0.0'),
                            credit=rounded_actual
                        )
                    )
                    
                    variance_desc = ""
                    if usage.feed_variance_weight is not None and usage.feed_variance_weight != Decimal('0.0'):
                        variance_desc = f". Variance Weight: {usage.feed_variance_weight:+.3f} kg"

                    journal_entry = JournalEntryCreate(
                        date=used_at_dt.date() if isinstance(used_at_dt, datetime) else used_at_dt,
                        description=f"COGS for Composition '{usage.composition_name}' on Batch '{data.batch_no}'{variance_desc}",
                        reference_document=f"COMP-USAGE-{data.batch_no}",
                        items=journal_items
                    )
                    journal_entry_crud.create_journal_entry(db=db, entry=journal_entry, tenant_id=tenant_id)
                    logger.info(f"Created COGS Journal Entry for Usage {usage.id}: {rounded_actual} (standard: {rounded_standard if 'rounded_standard' in locals() else rounded_actual}, variance: {rounded_variance if 'rounded_variance' in locals() else 0.0})")
        except Exception as e:
            logger.error(f"Failed to create COGS journal entry for usage {usage.id}: {e}")
        # --- End Journal Entry ---

        return {"message": "Composition used and feed quantities updated", "usage_id": usage.id}
    else:
        # This fallback is for unexpected cases, indicating an issue in use_composition
        raise HTTPException(status_code=500, detail="Failed to retrieve usage ID after processing composition.")


@router.get("/{composition_id}/usage-history", response_model=PaginatedCompositionUsageHistoryResponse)
def get_composition_usage_history_endpoint(
    composition_id: int,
    offset: int = 0,
    limit: int = 10,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return get_composition_usage_history(db, tenant_id, composition_id=composition_id, offset=offset, limit=limit, start_date=start_date, end_date=end_date)

@router.get("/usage-history", response_model=PaginatedCompositionUsageHistoryResponse)
def get_all_composition_usage_history(
    offset: int = 0,
    limit: int = 10,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return get_composition_usage_history(db, tenant_id=tenant_id, offset=offset, limit=limit, start_date=start_date, end_date=end_date)

@router.get("/usage-history/filtered", response_model=list[CompositionUsageHistory])
def get_filtered_composition_usage_history(
    batch_date: date,
    batch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Get composition usage history for a specific date, with an optional filter for batch_id.
    """
    # Import is now at the top of the file

    # Define the time range for the given date
    start_of_day = datetime.combine(batch_date, datetime.min.time())
    end_of_day = datetime.combine(batch_date, datetime.max.time())

    query = db.query(CompositionUsageHistoryModel).filter(CompositionUsageHistoryModel.tenant_id == tenant_id)
    
    # Filter by date range (start and end of the given day)
    query = query.filter(CompositionUsageHistoryModel.used_at >= start_of_day)
    query = query.filter(CompositionUsageHistoryModel.used_at <= end_of_day)

    if batch_id:
        query = query.filter(CompositionUsageHistoryModel.batch_id == batch_id)

    return query.order_by(CompositionUsageHistoryModel.used_at.desc()).all()

@router.post("/revert-usage/{usage_id}")
def revert_composition_usage_endpoint(
    usage_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Reverts a specific composition usage by ID.
    Adds back the quantities to feeds and deletes the usage history record.
    """
    success, message = revert_composition_usage(db, usage_id, changed_by=get_user_identifier(user), tenant_id=tenant_id)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}

@router.get("/usage-by-date", response_model=CompositionUsageByDate)
def get_usage_by_date_endpoint(
    usage_date: date,
    batch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return get_composition_usage_by_date(db, usage_date, tenant_id, batch_id=batch_id)
