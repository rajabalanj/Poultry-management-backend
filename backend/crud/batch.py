from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from models.batch import Batch
from schemas.batch import BatchCreate
from datetime import date
import routers.reports as reports
from models.daily_batch import DailyBatch

def get_batch(db: Session, batch_id: int, batch_date: date):
        return db.query(DailyBatch).filter(and_(DailyBatch.batch_id == batch_id, DailyBatch.batch_date == batch_date)).first()

def get_all_batches(db: Session, batch_date: date, skip: int = 0, limit: int = 100,):
    query = db.query(DailyBatch).join(Batch).filter(
        DailyBatch.batch_date == batch_date, Batch.is_active
    )
    daily_batches = query.offset(skip).limit(limit).all()
    for daily in daily_batches:
        # Convert batch_no like 'B-0001' to integer 1
        if daily.batch_no and str(daily.batch_no).startswith('B-'):
            daily.batch_no = int(daily.batch_no.split('-')[1].lstrip('0') or '0')
    return daily_batches

def create_batch(db: Session, batch: BatchCreate, changed_by: str = None):
    # Create new batch with calculated closing count
    db_batch = Batch(
        age=batch.age,
        batch_no =  batch.batch_no,
        opening_count=batch.opening_count,
        shed_no=batch.shed_no,
        date= batch.date,
        # standard_hen_day_percentage=batch.standard_hen_day_percentage if hasattr(batch, 'standard_hen_day_percentage') else 0.0
    )
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)

    # Create a copy in daily_batch table
    db_daily_batch = DailyBatch(
        batch_id=db_batch.id,
        batch_no=db_batch.batch_no,
        shed_no=db_batch.shed_no,
        batch_date=db_batch.date,
        upload_date=db_batch.date,
        age=db_batch.age,
        opening_count=db_batch.opening_count,
        mortality=0,
        culls=0,
        table_eggs=0,
        jumbo=0,
        cr=0,
    )
    db.add(db_daily_batch)
    db.commit()
    db.refresh(db_daily_batch)
    return db_batch

def update_batch(db: Session, batch_id: int, batch_date: date, batch_data: dict, changed_by: str = None):
    # Find today's daily_batch row for this batch_id

    db_daily_batch = db.query(DailyBatch).filter(DailyBatch.batch_id == batch_id, DailyBatch.batch_date == batch_date).first()
    if db_daily_batch:
        # Update fields
        for key, value in batch_data.items():
            if hasattr(db_daily_batch, key):
                setattr(db_daily_batch, key, value)
        # Recalculate closing_count and hd
        # db_daily_batch.closing_count = int(db_daily_batch.opening_count) - (int(db_daily_batch.mortality) + int(db_daily_batch.culls))
        # db_daily_batch.hd = (int(db_daily_batch.table_eggs) + int(db_daily_batch.jumbo) + int(db_daily_batch.cr)) / db_daily_batch.closing_count if db_daily_batch.closing_count > 0 else 0
    else:
        db_daily_batch = DailyBatch(
            batch_id=batch_id,
            batch_no=batch_data.get('batch_no', None),
            shed_no=batch_data.get('shed_no', None),
            batch_date=batch_date,
            upload_date=date.today(),
            age=batch_data.get('age', None),
            opening_count=batch_data.get('opening_count', 0),
            mortality=batch_data.get('mortality', 0),
            culls=batch_data.get('culls', 0),
            closing_count=batch_data.get('opening_count', 0) - (batch_data.get('mortality', 0) + batch_data.get('culls', 0)),
            table_eggs=batch_data.get('table_eggs', 0),
            jumbo=batch_data.get('jumbo', 0),
            cr=batch_data.get('cr', 0),
            hd=(batch_data.get('table_eggs', 0) + batch_data.get('jumbo', 0) + batch_data.get('cr', 0)) / (batch_data.get('opening_count', 0) - (batch_data.get('mortality', 0) + batch_data.get('culls', 0))) if (batch_data.get('opening_count', 0) - (batch_data.get('mortality', 0) + batch_data.get('culls', 0))) > 0 else 0,
        )
        db.add(db_daily_batch)
    db.commit()
    db.refresh(db_daily_batch)
    return db_daily_batch

def delete_batch(db: Session, batch_id: int, changed_by: str = None):
    db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if db_batch:
        db.delete(db_batch)
        db.commit()
        batches = db.query(Batch).filter(Batch.date == date.today()).all()
        reports.write_daily_report_excel(batches)
        return True
    return False

