from sqlalchemy.orm import Session
from sqlalchemy import func
from models.daily_batch import DailyBatch
from schemas.daily_batch import DailyBatchCreate
from datetime import date
from typing import Optional
from models.daily_batch import DailyBatch as DailyBatchORM

def get_batch(db: Session, batch_id: int, date: date):
    return db.query(DailyBatch).filter(DailyBatch.id == batch_id).first()

def get_all_batches(db: Session, skip: int = 0, limit: int = 100):
    return db.query(DailyBatch).offset(skip).limit(limit).all()


def update_batch_history(db: Session, batch_id: int, date: date, opening_count: int, age: float, mortality_count: int, culls_count: int, table_egg_count: int, jumbo_egg_count: int, cracked_egg_count: int, closing_count: int, hd: float):
    batch_history = DailyBatch(batch_id=batch_id, date=date, opening_count=opening_count, age=age, mortality_count=mortality_count, culls_count=culls_count, table_egg_count=table_egg_count, jumbo_egg_count=jumbo_egg_count, cracked_egg_count=cracked_egg_count, closing_count=closing_count, hd=hd)
    db.session.add(batch_history)
    db.session.commit()

def create_daily_batch(db: Session, daily_batch_data: DailyBatchCreate, changed_by: Optional[str] = None):
    """
    Creates a single daily batch record in the database.
    Expects a Pydantic DailyBatchCreate model instance.
    """
    # Now, daily_batch_data is a Pydantic object, so you can use dot notation directly.
    # No need for hasattr or getattr anymore!
    db_daily_batch = DailyBatchORM(
        batch_id=daily_batch_data.batch_id,
        batch_date=daily_batch_data.batch_date,
        upload_date=daily_batch_data.upload_date,
        shed_no=daily_batch_data.shed_no,
        batch_no=daily_batch_data.batch_no,
        age=daily_batch_data.age,
        opening_count=daily_batch_data.opening_count,
        mortality=daily_batch_data.mortality,
        culls=daily_batch_data.culls,
        # These calculations should ideally be done before creating the Pydantic model
        # in the FastAPI endpoint, and passed as already calculated values.
        # However, if your Pydantic model (DailyBatchCreate) doesn't include them,
        # or if you want to re-calculate them here, ensure daily_batch_data has the raw values.
        # Based on your previous code, these are already calculated in the endpoint
        # and passed into the DailyBatchCreate instance.
        closing_count=daily_batch_data.closing_count,
        table_eggs=daily_batch_data.table_eggs,
        jumbo=daily_batch_data.jumbo,
        cr=daily_batch_data.cr,
        hd=daily_batch_data.hd,
        is_chick_batch=daily_batch_data.is_chick_batch # This should be directly from the Pydantic model
    )
    db.add(db_daily_batch)
    db.commit()
    db.refresh(db_daily_batch)
    return db_daily_batch

# You do NOT have create_multiple_daily_batches, so it's removed from this file.