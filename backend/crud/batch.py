from sqlalchemy.orm import Session
from sqlalchemy import func
from models.batch import Batch
from schemas.batch import BatchCreate
from datetime import date
import reports

def get_batch(db: Session, batch_id: int):
    return db.query(Batch).filter(Batch.id == batch_id).first()

def get_all_batches(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Batch).offset(skip).limit(limit).all()

def get_next_batch_number(db: Session) -> str:
    # Get the highest batch number
    last_batch = db.query(Batch).order_by(Batch.batch_no.desc()).first()
    if last_batch and last_batch.batch_no:
        try:
            last_num = int(last_batch.batch_no.split('-')[1])
            return f"B-{str(last_num + 1).zfill(4)}"
        except (IndexError, ValueError):
            return "B-0001"
    return "B-0001"

def create_batch(db: Session, batch: BatchCreate, changed_by: str = None):
    # Get the next batch number
    new_batch_no = get_next_batch_number(db)

    # Create new batch with calculated closing count
    db_batch = Batch(
        age=batch.age,
        opening_count=batch.opening_count,
        mortality=batch.mortality,
        culls=batch.culls,
        closing_count=batch.opening_count - (batch.mortality + batch.culls),
        HD=batch.total_eggs / batch.closing_count if batch.closing_count > 0 else 0,
        shed_no=batch.shed_no,
        batch_no=new_batch_no,
        date=date.today()
    )
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)
    batches = db.query(Batch).filter(Batch.date == date.today()).all()
    reports.write_daily_report_excel(batches)
    return db_batch

def update_batch(db: Session, batch_id: int, batch_data: dict, changed_by: str = None):
    db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not db_batch:
        return None

    # Update the provided fields
    for key, value in batch_data.items():
        setattr(db_batch, key, value)
    
    # Recalculate closing count
    db_batch.closing_count = db_batch.opening_count - (db_batch.mortality + db_batch.culls)
    db_batch.HD = db_batch.total_eggs / db_batch.closing_count if db_batch.closing_count > 0 else 0
    db.commit()
    db.refresh(db_batch)
    batches = db.query(Batch).filter(Batch.date == date.today()).all()
    reports.write_daily_report_excel(batches)
    return db_batch

def delete_batch(db: Session, batch_id: int, changed_by: str = None):
    db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if db_batch:
        db.delete(db_batch)
        db.commit()
        batches = db.query(Batch).filter(Batch.date == date.today()).all()
        reports.write_daily_report_excel(batches)
        return True
    return False 

