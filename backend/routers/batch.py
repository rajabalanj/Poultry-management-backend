# Standard library imports
import logging
from datetime import date, datetime, timedelta
from typing import List

# Third-party imports
import pytz
from dateutil import parser
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

# Local application imports
import crud.batch as crud_batch
from crud.audit_log import create_audit_log
from database import get_db
from models.batch import Batch as BatchModel
from models.batch_shed_assignment import BatchShedAssignment
from models.daily_batch import DailyBatch as DailyBatchModel
from models.shed import Shed
from schemas.audit_log import AuditLogCreate
from schemas.batch import BatchCreate, Batch as BatchSchema, BatchResponse
from utils.auth_utils import get_current_user, get_user_identifier, require_group
from utils.tenancy import get_tenant_id
from utils import sqlalchemy_to_dict, calculate_age_progression

# --- Logging Configuration ---
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
    user_identifier = get_user_identifier(user)
    now = datetime.now(pytz.timezone('Asia/Kolkata'))

    # 1. Validation
    if not batch.batch_no or not batch.batch_no.strip():
        raise HTTPException(status_code=400, detail="Batch number cannot be empty.")

    # Check for active batch with the same batch_no
    existing_batch_no = db.query(BatchModel).filter(
        BatchModel.batch_no == batch.batch_no,
        BatchModel.is_active == True,
        BatchModel.tenant_id == tenant_id
    ).first()
    if existing_batch_no:
        raise HTTPException(status_code=400, detail=f"An active batch with batch number '{batch.batch_no}' already exists.")

    # Check if the shed is occupied on the batch start date
    conflicting_assignment = db.query(BatchShedAssignment).join(BatchModel).filter(
        BatchShedAssignment.shed_id == batch.shed_id,
        BatchShedAssignment.start_date <= batch.date,
        (BatchShedAssignment.end_date == None) | (BatchShedAssignment.end_date >= batch.date),
        BatchModel.is_active == True,
        BatchModel.tenant_id == tenant_id
    ).first()

    if conflicting_assignment:
        conflicting_batch = conflicting_assignment.batch
        shed = db.query(Shed).filter(Shed.id == batch.shed_id).first()
        shed_no = shed.shed_no if shed else f"ID {batch.shed_id}"
        raise HTTPException(status_code=400, detail=f"Shed '{shed_no}' is already occupied by active batch '{conflicting_batch.batch_no}' on the selected start date.")

    if batch.age < 0:
        raise HTTPException(status_code=400, detail="Age must be a non-negative number.")

    # 2. Execution
    try:
        # Step 2a: Create the Batch object
        batch_data = batch.model_dump()
        shed_id = batch_data.pop("shed_id")
        db_batch = BatchModel(
            **batch_data,
            tenant_id=tenant_id,
            created_by=user_identifier,
            updated_by=user_identifier,
            created_at=now,
            updated_at=now
        )
        db.add(db_batch)
        db.flush() # Use flush to get the db_batch.id for the next steps

        # Step 2b: Create the initial shed assignment
        db_shed_assignment = BatchShedAssignment(
            batch_id=db_batch.id,
            shed_id=shed_id,
            start_date=db_batch.date,
            end_date=None,
            created_by=user_identifier,
            updated_by=user_identifier,
            created_at=now,
            updated_at=now
        )
        db.add(db_shed_assignment)

        # Step 2c: Create the initial entry in the daily_batch table
        db_daily_batch = DailyBatchModel(
            batch_id=db_batch.id,
            tenant_id=tenant_id,
            batch_no=db_batch.batch_no,
            shed_id=shed_id,
            batch_date=db_batch.date,
            upload_date=db_batch.date,
            age=db_batch.age,
            opening_count=db_batch.opening_count,
            mortality=0,
            culls=0,
            table_eggs=0,
            jumbo=0,
            cr=0,
            created_by=user_identifier,
            updated_by=user_identifier,
            created_at=now,
            updated_at=now
        )
        db.add(db_daily_batch)

        # Step 2d: Create audit log
        new_values = sqlalchemy_to_dict(db_batch)
        log_entry = AuditLogCreate(
            table_name='batch',
            record_id=str(db_batch.id),
            changed_by=user_identifier,
            action='CREATE',
            old_values=None,
            new_values=new_values
        )
        # This function likely handles its own commit, or we can commit at the end
        create_audit_log(db=db, log_entry=log_entry)

        db.commit()
        db.refresh(db_batch)
        
        return db_batch

    except Exception as e:
        db.rollback()
        logger.exception("Error creating batch: %s", e)
        raise HTTPException(status_code=500, detail="An internal error occurred while creating the batch.")

@router.get("/all/", response_model=List[BatchResponse])
def get_all_batches(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Fetch all batches with pagination, including current shed info and active status.
    """
    # Get all batches
    batches = db.query(BatchModel).filter(BatchModel.tenant_id == tenant_id).order_by(BatchModel.batch_no).offset(skip).limit(limit).all()
    
    batch_ids = [b.id for b in batches]
    
    # Get current shed assignments for these batches
    assignments = db.query(BatchShedAssignment).filter(
        BatchShedAssignment.batch_id.in_(batch_ids),
        BatchShedAssignment.end_date == None
    ).all()
    
    # Get shed details for the assignments
    shed_ids = [a.shed_id for a in assignments]
    sheds = db.query(Shed).filter(Shed.id.in_(shed_ids)).all()
    shed_map = {s.id: s for s in sheds}
    
    assignment_map = {a.batch_id: a for a in assignments}
    
    result = []
    for batch in batches:
        assignment = assignment_map.get(batch.id)
        shed_info = None
        if assignment:
            shed = shed_map.get(assignment.shed_id)
            if shed:
                shed_info = {"id": shed.id, "shed_no": shed.shed_no}
        
        batch_data = {
            "id": batch.id,
            "age": batch.age,
            "opening_count": batch.opening_count,
            "batch_no": batch.batch_no,
            "date": batch.date,
            "tenant_id": batch.tenant_id,
            "batch_type": batch.batch_type,
            "current_shed": shed_info,
            "is_active": batch.is_active
        }
        result.append(batch_data)
        
    return result

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

@router.get("/{batch_id}", response_model=BatchResponse)
def read_batch(batch_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    logger.info("Fetching batch with batch_id=%d", batch_id)
    db_batch = db.query(BatchModel).filter(BatchModel.id == batch_id, BatchModel.tenant_id == tenant_id).first()
    if db_batch is None:
        logger.warning("Batch with batch_id=%d not found for tenant %s", batch_id, tenant_id)
        raise HTTPException(status_code=404, detail="Batch not found")
    logger.info("Fetched batch: %s", db_batch)
    
    # Get the current shed assignment for this batch
    assignment = db.query(BatchShedAssignment).filter(
        BatchShedAssignment.batch_id == batch_id,
        BatchShedAssignment.end_date == None
    ).first()
    
    shed_info = None
    if assignment:
        shed = db.query(Shed).filter(Shed.id == assignment.shed_id).first()
        if shed:
            shed_info = {"id": shed.id, "shed_no": shed.shed_no}
    
    batch_data = {
        "id": db_batch.id,
        "age": db_batch.age,
        "opening_count": db_batch.opening_count,
        "batch_no": db_batch.batch_no,
        "date": db_batch.date,
        "tenant_id": db_batch.tenant_id,
        "batch_type": db_batch.batch_type,
        "current_shed": shed_info,
        "is_active": db_batch.is_active
    }
    
    return batch_data

@router.patch("/{batch_id}", response_model=BatchSchema)
def update_batch(
    batch_id: int,
    batch_data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin"])),
    tenant_id: str = Depends(get_tenant_id)
):
    # Imports are now at the top of the file

    logger.info(f"Update batch called for batch_id={batch_id} with data: {batch_data}")

    db_batch = db.query(BatchModel).filter(BatchModel.id == batch_id, BatchModel.tenant_id == tenant_id).first()
    if db_batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    if not db_batch.is_active:
        raise HTTPException(status_code=400, detail="Closed batches cannot be updated.")

    db_batch.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_batch.updated_by = get_user_identifier(user)
    
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

    if not changes:
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
        # Handle BatchShedAssignment update if batch date changes
        if 'date' in changes:
            # Find the BatchShedAssignment that started on the old_date of the batch
            initial_assignment = db.query(BatchShedAssignment).filter(
                BatchShedAssignment.batch_id == batch_id,
                BatchShedAssignment.start_date == old_date,
                BatchShedAssignment.batch.has(tenant_id=tenant_id)
            ).first()

            if initial_assignment:
                initial_assignment.start_date = new_date
                db.add(initial_assignment)
                logger.info(f"Updated initial BatchShedAssignment start_date for batch {batch_id} from {old_date} to {new_date}")
                db.flush()
            else:
                logger.warning(f"No BatchShedAssignment found starting on {old_date} for batch {batch_id} when batch date was changed. This might lead to issues.")
        
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
            assignment = db.query(BatchShedAssignment).filter(
                BatchShedAssignment.batch_id == batch_id,
                BatchShedAssignment.start_date <= new_date,
                (BatchShedAssignment.end_date == None) | (BatchShedAssignment.end_date >= new_date)
            ).order_by(BatchShedAssignment.start_date.desc()).first()

            if not assignment:
                raise HTTPException(status_code=409, detail=f"Cannot find a shed assignment for the batch on date {new_date}.")
            
            current_shed_id = assignment.shed_id
            start_row = DailyBatchModel(batch_id=batch_id, tenant_id=tenant_id, batch_date=new_date, batch_no=db_batch.batch_no, shed_id=current_shed_id)
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
                prev_age = prev_row.age
                new_age = calculate_age_progression(prev_age, days_diff)
                current_row.age = new_age
            
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
        # Import is now at the top of the file
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

    logger.info(f"Successfully updated batch {batch_id}.")
    return db_batch

# Imports are now at the top of the file

class BatchMovePayload(BaseModel):
    new_shed_id: int
    move_date: date

@router.post("/{batch_id}/move-shed", summary="Move a batch to a new shed from a specific date onwards")
def move_shed(
    batch_id: int,
    payload: BatchMovePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin"])),
    tenant_id: str = Depends(get_tenant_id)
):
    # 1. Validation
    batch = db.query(BatchModel).filter(BatchModel.id == batch_id, BatchModel.tenant_id == tenant_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if not batch.is_active:
        raise HTTPException(status_code=400, detail="Cannot move a closed batch.")
    
    new_shed = db.query(Shed).filter(Shed.id == payload.new_shed_id, Shed.tenant_id == tenant_id).first()
    if not new_shed:
        raise HTTPException(status_code=404, detail="New shed not found.")

    if payload.move_date < batch.date:
        raise HTTPException(status_code=400, detail=f"Move date is before the batch start date {batch.date.strftime('%d-%m-%Y')}.")

    # Check for shed conflicts
    conflicting_assignment = db.query(BatchShedAssignment).join(BatchModel).filter(
        BatchShedAssignment.shed_id == payload.new_shed_id,
        BatchShedAssignment.batch_id != batch_id,
        (BatchShedAssignment.end_date == None) | (BatchShedAssignment.end_date >= payload.move_date),
        BatchModel.is_active == True,
        BatchModel.tenant_id == tenant_id
    ).first()

    if conflicting_assignment:
        raise HTTPException(status_code=409, detail=f"Shed '{new_shed.shed_no}' is occupied by batch '{conflicting_assignment.batch.batch_no}' during the selected period.")

    # 2. Execution
    # Find the assignment to be terminated or shortened
    assignment_to_end = db.query(BatchShedAssignment).filter(
        BatchShedAssignment.batch_id == batch_id,
        BatchShedAssignment.start_date < payload.move_date,
        (BatchShedAssignment.end_date == None) | (BatchShedAssignment.end_date >= payload.move_date)
    ).first()

    if not assignment_to_end:
        raise HTTPException(status_code=400, detail="Could not find a current shed assignment for the batch on the specified move date.")

    if assignment_to_end.shed_id == payload.new_shed_id:
        raise HTTPException(status_code=400, detail="Batch is already assigned to this shed.")

    # End the old assignment
    assignment_to_end.end_date = payload.move_date - timedelta(days=1)
    assignment_to_end.updated_by = get_user_identifier(user)
    db.add(assignment_to_end)

    # Create the new assignment
    new_assignment = BatchShedAssignment(
        batch_id=batch_id,
        shed_id=payload.new_shed_id,
        start_date=payload.move_date,
        end_date=None,
        created_by=get_user_identifier(user),
        updated_by=get_user_identifier(user)
    )
    db.add(new_assignment)

    # 3. Update DailyBatch records
    db.query(DailyBatchModel).filter(
        DailyBatchModel.batch_id == batch_id,
        DailyBatchModel.batch_date >= payload.move_date
    ).update({"shed_id": payload.new_shed_id})

    db.commit()

    return {"message": f"Batch '{batch.batch_no}' successfully moved to shed '{new_shed.shed_no}' from {payload.move_date}."}


class BatchSwapPayload(BaseModel):
    batch_id_1: int
    batch_id_2: int
    swap_date: date

@router.post("/swap-sheds", summary="Swap the sheds of two active batches from a specific date onwards")
def swap_sheds(
    payload: BatchSwapPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(require_group(["admin"])),
    tenant_id: str = Depends(get_tenant_id)
):
    user_identifier = get_user_identifier(user)
    
    # 1. Validation
    if payload.batch_id_1 == payload.batch_id_2:
        raise HTTPException(status_code=400, detail="Cannot swap a batch with itself.")

    batch1 = db.query(BatchModel).filter(BatchModel.id == payload.batch_id_1, BatchModel.tenant_id == tenant_id).first()
    batch2 = db.query(BatchModel).filter(BatchModel.id == payload.batch_id_2, BatchModel.tenant_id == tenant_id).first()

    if not batch1 or not batch2:
        raise HTTPException(status_code=404, detail="One or both batches not found.")
    if not batch1.is_active or not batch2.is_active:
        raise HTTPException(status_code=400, detail="One or both batches are not active.")

    if payload.swap_date < batch1.date.date() or payload.swap_date < batch2.date.date():
        raise HTTPException(status_code=400, detail="Swap date cannot be before the start date of either batch.")

    # Find current assignments for both batches
    assignment1 = db.query(BatchShedAssignment).filter(BatchShedAssignment.batch_id == payload.batch_id_1, BatchShedAssignment.end_date == None).first()
    assignment2 = db.query(BatchShedAssignment).filter(BatchShedAssignment.batch_id == payload.batch_id_2, BatchShedAssignment.end_date == None).first()

    if not assignment1 or not assignment2:
        raise HTTPException(status_code=400, detail="Could not find current shed assignments for one or both batches.")

    shed1_id = assignment1.shed_id
    shed2_id = assignment2.shed_id

    # 2. Execution
    # End old assignments
    assignment1.end_date = payload.swap_date - timedelta(days=1)
    assignment1.updated_by = user_identifier
    db.add(assignment1)

    assignment2.end_date = payload.swap_date - timedelta(days=1)
    assignment2.updated_by = user_identifier
    db.add(assignment2)

    # Create new assignments
    new_assignment1 = BatchShedAssignment(batch_id=payload.batch_id_1, shed_id=shed2_id, start_date=payload.swap_date, created_by=user_identifier, updated_by=user_identifier)
    new_assignment2 = BatchShedAssignment(batch_id=payload.batch_id_2, shed_id=shed1_id, start_date=payload.swap_date, created_by=user_identifier, updated_by=user_identifier)
    db.add(new_assignment1)
    db.add(new_assignment2)

    # 3. Update DailyBatch records
    db.query(DailyBatchModel).filter(DailyBatchModel.batch_id == payload.batch_id_1, DailyBatchModel.batch_date >= payload.swap_date).update({"shed_id": shed2_id})
    db.query(DailyBatchModel).filter(DailyBatchModel.batch_id == payload.batch_id_2, DailyBatchModel.batch_date >= payload.swap_date).update({"shed_id": shed1_id})

    db.commit()

    return {"message": f"Successfully swapped sheds for batches '{batch1.batch_no}' and '{batch2.batch_no}' from {payload.swap_date}."}



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

class BatchClosePayload(BaseModel):
    closing_date: date

@router.post("/{batch_id}/close")
def close_batch(
    batch_id: int, 
    payload: BatchClosePayload,
    db: Session = Depends(get_db), 
    tenant_id: str = Depends(get_tenant_id), 
    user: dict = Depends(require_group(["admin"]))
):
    batch = db.query(BatchModel).filter(BatchModel.id == batch_id, BatchModel.tenant_id == tenant_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if not batch.is_active:
        raise HTTPException(status_code=400, detail="Batch is already closed.")

    closing_date = payload.closing_date
    
    # Validation
    if closing_date > date.today():
        raise HTTPException(status_code=400, detail="Closing date cannot be in the future.")
    
    batch_start_date = batch.date if isinstance(batch.date, date) else batch.date.date()
    if closing_date < batch_start_date:
        raise HTTPException(status_code=400, detail=f"Closing date cannot be before the batch start date of {batch_start_date}.")

    # Delete future daily_batch entries if closing retroactively
    db.query(DailyBatchModel).filter(
        DailyBatchModel.batch_id == batch_id,
        DailyBatchModel.tenant_id == tenant_id,
        DailyBatchModel.batch_date > closing_date
    ).delete(synchronize_session=False)

    batch.closing_date = closing_date  # This will automatically set is_active to False
    batch.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    batch.updated_by = get_user_identifier(user)

    # Find and end the current shed assignment
    current_assignment = db.query(BatchShedAssignment).filter(
        BatchShedAssignment.batch_id == batch_id,
        BatchShedAssignment.end_date == None,
        BatchShedAssignment.batch.has(tenant_id=tenant_id) # Ensure tenancy
    ).first()

    if current_assignment:
        current_assignment.end_date = closing_date
        current_assignment.updated_by = get_user_identifier(user)
        db.add(current_assignment)

    db.add(batch)
    db.commit()
    
    return {"message": f"Batch '{batch.batch_no}' closed successfully on {closing_date}."}

