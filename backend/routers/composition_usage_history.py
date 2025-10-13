from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from crud.composition_usage_history import use_composition, get_composition_usage_history, revert_composition_usage, get_composition_usage_by_date
from schemas.composition_usage_history import CompositionUsageHistory
from utils.auth_utils import get_current_user, get_user_identifier
from utils.tenancy import get_tenant_id
from datetime import datetime, date
from dateutil import parser
from models.batch import Batch as BatchModel

router = APIRouter(
    prefix="/compositions",
    tags=["Composition Usage History"],
)

@router.post("/use-composition")
def use_composition_endpoint(
    data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    composition_id = data["compositionId"]
    shed_no = data["shed_no"]
    times = data["times"]
    used_at = data.get("usedAt")

    if used_at:
        try:
            used_at_dt = datetime.fromisoformat(used_at)
        except ValueError:
            used_at_dt = parser.parse(used_at)
    else:
        used_at_dt = datetime.now()

    # Find the batch_id based on shed_no
    batch = db.query(BatchModel).filter(BatchModel.shed_no == shed_no, BatchModel.is_active, BatchModel.tenant_id == tenant_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Active batch with shed_no '{shed_no}' not found.")
    batch_id = batch.id

    # Call use_composition and pass changed_by (user from token)
    usage = use_composition(db, composition_id, batch_id, times, used_at_dt, changed_by=get_user_identifier(user), tenant_id=tenant_id)
    
    # Now, 'usage' object should have its ID populated
    if usage and hasattr(usage, 'id'):
        return {"message": "Composition used and feed quantities updated", "usage_id": usage.id}
    else:
        # This fallback is for unexpected cases, indicating an issue in use_composition
        raise HTTPException(status_code=500, detail="Failed to retrieve usage ID after processing composition.")


@router.get("/{composition_id}/usage-history", response_model=list[CompositionUsageHistory])
def get_composition_usage_history_endpoint(
    composition_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return get_composition_usage_history(db, tenant_id, composition_id=composition_id)

@router.get("/usage-history", response_model=list[CompositionUsageHistory])
def get_all_composition_usage_history(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return get_composition_usage_history(db, tenant_id=tenant_id)

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
    from models.composition_usage_history import CompositionUsageHistory as CompositionUsageHistoryModel

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

@router.get("/usage-by-date/")
def get_usage_by_date_endpoint(
    usage_date: date,
    batch_id: Optional[int] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    return get_composition_usage_by_date(db, usage_date, tenant_id, batch_id=batch_id)
