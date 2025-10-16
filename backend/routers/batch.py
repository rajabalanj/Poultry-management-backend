import pytz
from models.daily_batch import DailyBatch as DailyBatchModel
from fastapi import APIRouter, Depends, HTTPException
from utils.auth_utils import get_current_user, get_user_identifier, require_group
from sqlalchemy.orm import Session
from models.batch import Batch as BatchModel
from schemas.batch import BatchCreate, Batch as BatchSchema
from datetime import date, datetime
from typing import List
import crud.batch as crud_batch
from database import get_db
from utils.tenancy import get_tenant_id
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict

# --- Logging Configuration (import and get logger) ---
import logging
logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/batches",
    tags=["Batches"],
    dependencies=[Depends(get_current_user)]
)

@router.post("/", response_model=BatchSchema)
def create_batch(
    batch: BatchCreate, 
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    # Application-level uniqueness check for active batches
    existing = db.query(BatchModel).filter(
        ((BatchModel.shed_no == batch.shed_no) | (BatchModel.batch_no == batch.batch_no)) & 
        (BatchModel.is_active) &
        (BatchModel.tenant_id == tenant_id)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="An active batch with the same shed_no or batch_no already exists.")
    return crud_batch.create_batch(db=db, batch=batch, tenant_id=tenant_id, changed_by=get_user_identifier(user))

@router.get("/all/", response_model=List[BatchSchema])
def get_all_batches(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Fetch all active batches with pagination.
    """
    try:
        # Filter by the is_active hybrid property
        batches = db.query(BatchModel).filter(BatchModel.is_active, BatchModel.tenant_id == tenant_id).order_by(BatchModel.batch_no).offset(skip).limit(limit).all()
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
        logger.exception(f"Error fetching active batches (skip={skip}, limit={limit}): {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching active batches.")

@router.get("/")
def read_batches(batch_date: date, skip: int = 0, limit: int = 100, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    logger.info("Fetching batches with skip=%d, limit=%d, batch_date=%s", skip, limit, batch_date)
    batches = crud_batch.get_all_batches(db, skip=skip, limit=limit, batch_date=batch_date, tenant_id=tenant_id)
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
def read_batch(batch_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    logger.info("Fetching batch with batch_id=%d", batch_id)
    db_batch = db.query(BatchModel).filter(BatchModel.id == batch_id, BatchModel.tenant_id == tenant_id).first()
    if db_batch is None:
        logger.warning("Batch with batch_id=%d not found for tenant %s", batch_id, tenant_id)
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
    user: dict = Depends(require_group(["admin"])),
    tenant_id: str = Depends(get_tenant_id)
):
    from utils import calculate_age_progression
    from dateutil import parser

    logger.info(f"Update batch called for batch_id={batch_id} with data: {batch_data}")

    db_batch = db.query(BatchModel).filter(BatchModel.id == batch_id, BatchModel.tenant_id == tenant_id).first()
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    db_batch.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_batch.updated_by = get_user_identifier(user)
    logger.info(f"Batch found: {db_batch.batch_no}, current shed_no: {db_batch.shed_no}")

    # Handle shed_no update with a specific date
    if 'shed_no' in batch_data:
        if 'shed_change_date' not in batch_data:
            raise HTTPException(status_code=400, detail="shed_change_date is required when updating shed_no.")
        
        try:
            shed_change_date_obj = parser.parse(batch_data['shed_change_date']).date()
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid shed_change_date format.")

        new_shed_no = batch_data['shed_no']

        # 1. Log and Update historical and future DailyBatch records
        daily_batches_to_update = db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date >= shed_change_date_obj,
            DailyBatchModel.tenant_id == tenant_id
        ).all()
        
        logger.info(f"Found {len(daily_batches_to_update)} DailyBatch rows to update.")
        for row in daily_batches_to_update:
            logger.info(f"  - DailyBatch with date: {row.batch_date}, Old shed_no: {row.shed_no}, New shed_no: {new_shed_no}")

        rows_updated = db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date >= shed_change_date_obj,
            DailyBatchModel.tenant_id == tenant_id
        ).update({'shed_no': new_shed_no}, synchronize_session=False)
        db.flush()
        logger.info("Updated %d DailyBatch rows for batch_id=%s from date %s for tenant=%s",
                    rows_updated, batch_id, shed_change_date_obj, tenant_id)

        # 2. Update the shed_no on the parent Batch record
        logger.info(f"Updating Batch {batch_id} shed_no from {db_batch.shed_no} to {new_shed_no}")
        db_batch.shed_no = new_shed_no
        db.flush()
        # Ensure the parent batch is in the session so change will be persisted
        try:
            db.add(db_batch)
        except Exception:
            logger.exception("Failed to add db_batch to session after shed_no change for batch_id=%s", batch_id)
        
        logger.info(f"Batch {batch_id} shed_no is now: {db_batch.shed_no}")
        # Remove these from batch_data so they are not processed again
        del batch_data['shed_no']
        if 'shed_change_date' in batch_data:
            del batch_data['shed_change_date']

    # --- 1. Calculate changes and update the master Batch object ---
    changes = {}
    old_values = sqlalchemy_to_dict(db_batch)
    old_date = db_batch.date
    # Ensure old_date is a date object, not datetime
    if hasattr(old_date, 'date') and callable(old_date.date):
        old_date = old_date.date()
    
    for key, value in batch_data.items():
        if hasattr(db_batch, key):
            if key == 'batch_no' and getattr(db_batch, key) != value:
                raise HTTPException(status_code=400, detail="Updating batch_no is not allowed.")
            old_value = getattr(db_batch, key)
            if key == 'date' and isinstance(value, str):
                value = parser.parse(value).date()
            if old_value != value:
                changes[key] = {"old": old_value, "new": value}
                setattr(db_batch, key, value)

    if not changes and 'shed_no' not in batch_data: # if shed_no was the only change
        db.commit()
        db.refresh(db_batch)
        return db_batch

    new_date = db_batch.date
    # Ensure new_date is a date object, not datetime
    if hasattr(new_date, 'date') and callable(new_date.date):
        new_date = new_date.date()

    # --- 2. Handle date change: delete old daily entries ---
    # Use a bulk delete with synchronize_session=False to avoid stale session state
    if 'date' in changes and new_date > old_date:
        # Use 'fetch' to synchronize the session with the rows that will be deleted.
        # This issues a SELECT to find affected identities and removes them from the session
        # which prevents stale/duplicate objects later when we re-query/update rows.
        deleted_count = db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date < new_date,
            DailyBatchModel.tenant_id == tenant_id
        ).delete(synchronize_session='fetch')
        logger.info("Deleted %d old daily_batch rows for batch_id=%s, tenant=%s", deleted_count, batch_id, tenant_id)

    # --- 3. Propagation Logic ---
    if any(key in changes for key in ['date', 'age', 'opening_count', 'batch_no']):
        
        # Get all daily_batch rows from the new start date onwards
        all_rows = db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date >= new_date,
            DailyBatchModel.tenant_id == tenant_id
        ).order_by(DailyBatchModel.batch_date.asc()).all()

        # Find or create the row for the exact new start date
        start_row = None
        if all_rows and all_rows[0].batch_date == new_date:
            start_row = all_rows[0]
        else:
            start_row = DailyBatchModel(batch_id=batch_id, tenant_id=tenant_id, batch_date=new_date)
            db.add(start_row)
            db.flush()  # Flush the new row first
            # Re-query to get fresh instances and ensure the session identity map matches DB
            # expire_all ensures any cached instances are expired and reloaded from DB
            db.expire_all()
            all_rows = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id,
                DailyBatchModel.batch_date >= new_date,
                DailyBatchModel.tenant_id == tenant_id
            ).order_by(DailyBatchModel.batch_date.asc()).all()
            # start_row should now be the first element
            if all_rows:
                start_row = all_rows[0]

        # --- 4. Loop through all affected rows and apply changes ---
        prev_row = None
        for i, current_row in enumerate(all_rows):


            if i == 0: # This is the start_row
                current_row.age = db_batch.age
                current_row.opening_count = db_batch.opening_count
                if not current_row.upload_date:
                    current_row.upload_date = new_date
            else: # This is a subsequent row, propagate from prev_row
                current_row.opening_count = prev_row.closing_count

                days_diff = (current_row.batch_date - prev_row.batch_date).days
                prev_age = float(prev_row.age)
                new_age = calculate_age_progression(prev_age, days_diff)
                current_row.age = str(round(new_age, 1))
            
            prev_row = current_row

    # --- 5. Commit the transaction ---
    # Log some session state before attempting to commit to help diagnose
    try:
        new_objs = list(db.new)
        dirty_objs = list(db.dirty)
        deleted_objs = list(db.deleted)
        logger.debug("Session before commit: new=%d dirty=%d deleted=%d", len(new_objs), len(dirty_objs), len(deleted_objs))
        # Log identity keys for dirty objects (helps map to SQL UPDATEs)
        try:
            dirty_keys = [obj.__table__.name + str(tuple(getattr(obj, k.name) for k in obj.__table__.primary_key)) for obj in dirty_objs]
        except Exception:
            dirty_keys = [str(obj) for obj in dirty_objs]
        logger.debug("Dirty objects keys: %s", dirty_keys)

        db.commit()
    except Exception as e:
        # Specific handling for SQLAlchemy stale data errors to capture more context
        from sqlalchemy.orm.exc import StaleDataError
        if isinstance(e, StaleDataError):
            logger.exception("StaleDataError committing batch update for batch_id=%s: %s", batch_id, e)
            # For stale data errors, refresh the session and retry the operation once
            try:
                db.rollback()
                db.expire_all()
                logger.info("Retrying batch update for batch_id=%s after StaleDataError", batch_id)
                db.commit()
                logger.info("Successfully completed batch update retry for batch_id=%s", batch_id)
            except Exception as retry_error:
                logger.exception("Retry failed for batch_id=%s: %s", batch_id, retry_error)
                db.rollback()
                raise HTTPException(status_code=500, detail="Failed to update batch due to concurrent changes. Please retry")
        else:
            logger.exception("Error committing batch update for batch_id=%s: %s", batch_id, e)
            # Log a little more DB state to help debugging
            try:
                logger.debug("Session new objects: %s", [repr(x) for x in list(db.new)])
                logger.debug("Session dirty objects: %s", [repr(x) for x in list(db.dirty)])
                logger.debug("Session deleted objects: %s", [repr(x) for x in list(db.deleted)])
            except Exception:
                pass
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to update batch (commit error). Please retry")
    db.refresh(db_batch)

    new_values = sqlalchemy_to_dict(db_batch)
    log_entry = AuditLogCreate(
        table_name='batch',
        record_id=str(batch_id),
        changed_by=get_user_identifier(user),
        action='UPDATE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)

    logger.info(f"Successfully updated batch {batch_id}. New shed_no: {db_batch.shed_no}")
    return db_batch

@router.delete("/{batch_id}")
def delete_batch(
    batch_id: int, 
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin"])),
    tenant_id: str = Depends(get_tenant_id)
):
    success = crud_batch.delete_batch(db, batch_id=batch_id, tenant_id=tenant_id, changed_by=get_user_identifier(user))
    if not success:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {"message": "Batch deleted successfully"}

@router.put("/{batch_id}/close")
def close_batch(batch_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id), user: dict = Depends(require_group(["admin"]))):
    batch = db.query(BatchModel).filter(BatchModel.id == batch_id, BatchModel.tenant_id == tenant_id).first()
    if batch:
        batch.closing_date = date.today()
        batch.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
        batch.updated_by = get_user_identifier(user)
        db.add(batch)
        db.commit()
        return {"message": "Batch closed successfully"}
    else:
        raise HTTPException(status_code=404, detail="Batch not found")
