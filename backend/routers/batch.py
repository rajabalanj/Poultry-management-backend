from models.daily_batch import DailyBatch as DailyBatchModel
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from utils.auth_utils import get_current_user
from sqlalchemy.orm import Session
from models.batch import Batch as BatchModel
from schemas.batch import BatchCreate, Batch as BatchSchema
from datetime import date
from typing import List, Optional
import crud.batch as crud_batch  # Assuming BatchCreate and BatchSchema exist
from database import get_db
from schemas.bovanswhitelayerperformance import BovansPerformanceSchema, PaginatedBovansPerformanceResponse

# --- Logging Configuration (import and get logger) ---
import logging
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/batches",
    tags=["Batches"]
)

@router.post("/", response_model=BatchSchema)
def create_batch(
    batch: BatchCreate, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    # Application-level uniqueness check for active batches
    existing = db.query(BatchModel).filter(
        ((BatchModel.shed_no == batch.shed_no) | (BatchModel.batch_no == batch.batch_no)) & (BatchModel.is_active == True)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="An active batch with the same shed_no or batch_no already exists.")
    return crud_batch.create_batch(db=db, batch=batch, changed_by=user.get('sub'))

@router.get("/all/", response_model=List[BatchSchema])
def get_all_batches(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Fetch all active batches with pagination.
    """
    try:
        # Filter by the is_active hybrid property
        batches = db.query(BatchModel).filter(BatchModel.is_active == True).order_by(BatchModel.batch_no).offset(skip).limit(limit).all()
        result = []
        for batch in batches:
            d = batch.__dict__.copy()
            try:
                d['batch_type'] = batch.batch_type
            except Exception:
                d['batch_type'] = None
            d.pop('_sa_instance_state', None)
            result.append(d)
        return result
    except Exception as e:
        # It's good practice to log the full exception for debugging
        # Assuming you have a logger configured
        # import logging
        # logger = logging.getLogger(__name__)
        logger.exception(f"Error fetching active batches (skip={skip}, limit={limit}): {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching active batches.")
@router.get("/")
def read_batches(batch_date: date, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info("Fetching batches with skip=%d, limit=%d, batch_date=%s", skip, limit, batch_date)
    batches = crud_batch.get_all_batches(db, skip=skip, limit=limit, batch_date=batch_date)
    logger.info("Fetched %d batches", len(batches))
    result = []
    for batch in batches:
        d = batch.__dict__.copy()
        try:
            d['batch_type'] = batch.batch_type
        except Exception:
            d['batch_type'] = None
        d.pop('_sa_instance_state', None)
        result.append(d)
    return result

@router.get("/{batch_id}", response_model=BatchSchema)
def read_batch(batch_id: int, db: Session = Depends(get_db)):
    logger.info("Fetching batch with batch_id=%d", batch_id)
    db_batch = db.query(BatchModel).filter(BatchModel.id == batch_id).first()
    if db_batch is None:
        logger.warning("Batch with batch_id=%d not found", batch_id)
        raise HTTPException(status_code=404, detail="Batch not found")
    logger.info("Fetched batch: %s", db_batch)
    d = db_batch.__dict__.copy()
    try:
        d['batch_type'] = db_batch.batch_type
    except Exception:
        d['batch_type'] = None
    d.pop('_sa_instance_state', None)
    return d

@router.patch("/{batch_id}", response_model=BatchSchema)
def update_batch(
    batch_id: int,
    batch_data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    from utils import calculate_age_progression
    db_batch = db.query(BatchModel).filter(BatchModel.id == batch_id).first()
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    changes = {}
    old_date = db_batch.date
    new_date = batch_data.get("date")
    date_changed_and_increased = False
    if new_date:
        # Convert to date if string
        if isinstance(new_date, str):
            from dateutil import parser
            new_date = parser.parse(new_date).date()
        if new_date > old_date:
            date_changed_and_increased = True

    for key, value in batch_data.items():
        if hasattr(db_batch, key):
            old_value = getattr(db_batch, key)
            if old_value != value:
                changes[key] = {"old": old_value, "new": value}
                setattr(db_batch, key, value)

    if changes:
        # If date increased, delete old daily_batch entries and create one for new_date if not present
        if date_changed_and_increased:
            db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id,
                DailyBatchModel.batch_date < new_date
            ).delete(synchronize_session=False)
            db.commit()
            exists = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id,
                DailyBatchModel.batch_date == new_date
            ).first()
            if not exists:
                db_daily = DailyBatchModel(
                    batch_id=batch_id,
                    shed_no=db_batch.shed_no,
                    batch_no=db_batch.batch_no,
                    upload_date=new_date,
                    batch_date=new_date,
                    age=db_batch.age,
                    opening_count=db_batch.opening_count,
                    mortality=0,
                    culls=0,
                    table_eggs=0,
                    jumbo=0,
                    cr=0,
                )
                db.add(db_daily)
                db.commit()
        # Example: update daily_batch if certain fields changed
        if "shed_no" in changes or "batch_no" in changes:
            related_batches = db.query(DailyBatchModel).filter(DailyBatchModel.batch_id == batch_id).all()
            for rel in related_batches:
                if "shed_no" in changes:
                    rel.shed_no = changes["shed_no"]["new"]
                if "batch_no" in changes:
                    rel.batch_no = changes["batch_no"]["new"]
        # Age update logic for daily_batch
        if "age" in batch_data and new_date:
            target_row = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id,
                DailyBatchModel.batch_date == new_date
            ).first()
            if target_row:
                try:
                    new_age = float(batch_data["age"])
                except Exception:
                    new_age = 0.0
                target_row.age = str(round(new_age, 1))
                subsequent_rows = db.query(DailyBatchModel).filter(
                    DailyBatchModel.batch_id == batch_id,
                    DailyBatchModel.batch_date > new_date
                ).order_by(DailyBatchModel.batch_date.asc()).all()
                prev_date = new_date
                prev_age = new_age
                for row in subsequent_rows:
                    days_diff = (row.batch_date - prev_date).days
                    prev_age = calculate_age_progression(prev_age, days_diff)
                    row.age = str(round(prev_age, 1))
                    prev_date = row.batch_date
        # Opening count update logic for daily_batch
        if "opening_count" in batch_data and new_date:
            # Update opening_count for the given batch_id and batch_date
            target_row = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id,
                DailyBatchModel.batch_date == new_date
            ).first()
            if target_row:
                target_row.opening_count = batch_data["opening_count"]
                # Fetch all daily_batch rows for this batch_id ordered by batch_date
                all_rows = db.query(DailyBatchModel).filter(
                    DailyBatchModel.batch_id == batch_id
                ).order_by(DailyBatchModel.batch_date.asc()).all()
                # Find the index of the updated row
                idx = next((i for i, row in enumerate(all_rows) if row.batch_date == new_date), None)
                if idx is not None:
                    prev_row = all_rows[idx]
                    for next_row in all_rows[idx+1:]:
                        next_row.opening_count = prev_row.closing_count  # closing_count is a hybrid property
                        prev_row = next_row
        # Optional: insert change logs into audit table here
        # insert_audit_logs(batch_id, changes, user.get('sub'))
        db.commit()
        db.refresh(db_batch)

    return db_batch



@router.delete("/{batch_id}")
def delete_batch(
    batch_id: int, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    success = crud_batch.delete_batch(db, batch_id=batch_id, changed_by=user.get('sub'))
    if not success:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"message": "Batch deleted successfully"}

@router.put("/{batch_id}/close")
def close_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(BatchModel).get(batch_id)
    if batch:
        batch.closing_date = date.today()
        db.add(batch)
        db.commit()
        return {"message": "Batch closed successfully"}
    else:
        return {"error": "Batch not found"}, 404