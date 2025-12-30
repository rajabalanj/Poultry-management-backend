from sqlalchemy.orm import Session
from models.shed import Shed
from schemas.shed import ShedCreate, ShedUpdate

def get_shed(db: Session, shed_id: int, tenant_id: str):
    return db.query(Shed).filter(Shed.id == shed_id, Shed.tenant_id == tenant_id).first()

def get_shed_by_shed_no(db: Session, shed_no: str, tenant_id: str):
    return db.query(Shed).filter(Shed.shed_no == shed_no, Shed.tenant_id == tenant_id).first()

def get_sheds(db: Session, tenant_id: str, skip: int = 0, limit: int = 100):
    return db.query(Shed).filter(Shed.tenant_id == tenant_id).offset(skip).limit(limit).all()

from utils.auth_utils import get_user_identifier

def create_shed(db: Session, shed: ShedCreate, tenant_id: str, user: dict):
    user_identifier = get_user_identifier(user)
    db_shed = Shed(**shed.model_dump(), tenant_id=tenant_id, created_by=user_identifier, updated_by=user_identifier)
    db.add(db_shed)
    db.commit()
    db.refresh(db_shed)
    return db_shed

def update_shed(db: Session, shed_id: int, shed: ShedUpdate, tenant_id: str, user: dict):
    db_shed = db.query(Shed).filter(Shed.id == shed_id, Shed.tenant_id == tenant_id).first()
    if db_shed:
        update_data = shed.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_shed, key, value)
        db_shed.updated_by = get_user_identifier(user)
        db.commit()
        db.refresh(db_shed)
    return db_shed

from models.batch import Batch
from models.daily_batch import DailyBatch
from models.batch_shed_assignment import BatchShedAssignment

def delete_shed(db: Session, shed_id: int, tenant_id: str):
    # Check if the shed is being used in BatchShedAssignment or DailyBatch
    is_used_in_batch = db.query(BatchShedAssignment).join(Batch).filter(
        BatchShedAssignment.shed_id == shed_id,
        Batch.tenant_id == tenant_id
    ).first()
    is_used_in_daily_batch = db.query(DailyBatch).filter(DailyBatch.shed_id == shed_id, DailyBatch.tenant_id == tenant_id).first()

    if is_used_in_batch or is_used_in_daily_batch:
        return False, "Shed is in use and cannot be deleted."

    db_shed = db.query(Shed).filter(Shed.id == shed_id, Shed.tenant_id == tenant_id).first()
    if db_shed:
        db.delete(db_shed)
        db.commit()
        return True, "Shed deleted successfully."
    return False, "Shed not found."
