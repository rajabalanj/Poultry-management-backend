from sqlalchemy.orm import Session
from typing import List, Optional
from models.batch_history import BatchHistory
from schemas.batch_history import BatchHistoryCreate

def create_batch_history(db: Session, history: BatchHistoryCreate) -> BatchHistory:
    db_history = BatchHistory(
        batch_id=history.batch_id,
        batch_no=history.batch_no,
        action=history.action,
        changed_by=history.changed_by,
        previous_value=history.previous_value,
        new_value=history.new_value,
        additional_info=history.additional_info
    )
    db.add(db_history)
    db.commit()
    db.refresh(db_history)
    return db_history

def get_batch_history(db: Session, batch_id: int) -> List[BatchHistory]:
    """Get all history records for a specific batch"""
    return db.query(BatchHistory).filter(BatchHistory.batch_id == batch_id).all()

def get_all_history(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    action: Optional[str] = None
) -> List[BatchHistory]:
    """Get all history records with optional filtering by action"""
    query = db.query(BatchHistory)
    if action:
        query = query.filter(BatchHistory.action == action)
    return query.offset(skip).limit(limit).all() 