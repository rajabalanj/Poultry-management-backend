from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from database import get_db
from models.batch import Batch as BatchModel
from crud.medicine_usage_history import use_medicine, get_medicine_usage_history, revert_medicine_usage
from schemas.medicine_usage_history import MedicineUsageHistory, MedicineUsageHistoryCreate

router = APIRouter(prefix="/medicine", tags=["medicine usage"])
logger = logging.getLogger(__name__)

@router.post("/use-medicine", response_model=MedicineUsageHistory)
def use_medicine_endpoint(
    usage_data: MedicineUsageHistoryCreate,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    """
    Records usage of a specific medicine quantity for a given batch/shed.
    """
    batch_id = usage_data.batch_id
    used_at_dt = usage_data.used_at if usage_data.used_at else datetime.now()
    
    batch = db.query(BatchModel).filter(BatchModel.id == batch_id, BatchModel.is_active == True).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Active batch with ID '{batch_id}' not found.")

    try:
        usage = use_medicine(
            db,
            medicine_id=usage_data.medicine_id,
            batch_id=batch_id,
            used_quantity_grams=usage_data.used_quantity_grams,
            used_at=used_at_dt,
            changed_by=x_user_id
        )
        return usage
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error using medicine: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while recording medicine usage.")

@router.get("/usage-history", response_model=List[MedicineUsageHistory])
def get_all_medicine_usage_history_endpoint(
    db: Session = Depends(get_db)
):
    """
    Retrieves all medicine usage history records.
    """
    return get_medicine_usage_history(db)

@router.get("/{medicine_id}/usage-history", response_model=List[MedicineUsageHistory])
def get_single_medicine_usage_history_endpoint(
    medicine_id: int,
    db: Session = Depends(get_db)
):
    """
    Retrieves medicine usage history records for a specific medicine.
    """
    return get_medicine_usage_history(db, medicine_id)

@router.post("/revert-usage/{usage_id}")
def revert_medicine_usage_endpoint(
    usage_id: int,
    db: Session = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    """
    Reverts a specific medicine usage by ID, adding back quantities and auditing.
    """
    success, message = revert_medicine_usage(db, usage_id, changed_by=x_user_id)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"message": message}