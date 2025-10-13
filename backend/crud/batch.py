import datetime
import pytz
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict
from models.batch import Batch
from schemas.batch import BatchCreate
from datetime import date
import routers.reports as reports
from models.daily_batch import DailyBatch

def get_batch(db: Session, batch_id: int, batch_date: date, tenant_id: str):
        return db.query(DailyBatch).join(Batch).filter(and_(DailyBatch.batch_id == batch_id, DailyBatch.batch_date == batch_date, Batch.tenant_id == tenant_id)).first()

def get_batch_by_id(db: Session, batch_id: int, tenant_id: str):
    return db.query(Batch).filter(Batch.id == batch_id, Batch.tenant_id == tenant_id).first()

def get_all_batches(db: Session, batch_date: date, tenant_id: str, skip: int = 0, limit: int = 100,):
    query = db.query(DailyBatch).join(Batch).filter(
        DailyBatch.batch_date == batch_date, Batch.is_active, Batch.tenant_id == tenant_id
    )
    daily_batches = query.offset(skip).limit(limit).all()
    for daily in daily_batches:
        # Convert batch_no like 'B-0001' to integer 1
        if daily.batch_no and str(daily.batch_no).startswith('B-'):
            daily.batch_no = int(daily.batch_no.split('-')[1].lstrip('0') or '0')
    return daily_batches

def create_batch(db: Session, batch: BatchCreate, tenant_id: str, changed_by: str):
    # Create new batch with calculated closing count
    db_batch = Batch(
        **batch.model_dump(),
        tenant_id=tenant_id,
        created_by=changed_by,
        updated_by=changed_by
    )
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)

    # Create a copy in daily_batch table
    db_daily_batch = DailyBatch(
        batch_id=db_batch.id,
        tenant_id=tenant_id,
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
        created_by=changed_by,
        updated_by=changed_by
    )
    db.add(db_daily_batch)
    db.commit()
    db.refresh(db_daily_batch)
    return db_batch

def delete_batch(db: Session, batch_id: int, tenant_id: str, changed_by: str):
    db_batch = db.query(Batch).filter(Batch.id == batch_id, Batch.tenant_id == tenant_id).first()
    if db_batch:
        old_values = sqlalchemy_to_dict(db_batch)
        db_batch.deleted_at = datetime.now(pytz.timezone('Asia/Kolkata'))
        db_batch.deleted_by = changed_by
        new_values = sqlalchemy_to_dict(db_batch)
        log_entry = AuditLogCreate(
            table_name='batch',
            record_id=str(batch_id),
            changed_by=changed_by,
            action='DELETE',
            old_values=old_values,
            new_values=new_values
        )
        create_audit_log(db=db, log_entry=log_entry)
        db.commit()
        batches = db.query(Batch).filter(Batch.date == date.today(), Batch.tenant_id == tenant_id).all()
        reports.write_daily_report_excel(batches)
        return True
    return False

