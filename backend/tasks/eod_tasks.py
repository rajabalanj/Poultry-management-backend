from datetime import datetime
from decimal import Decimal, localcontext, ROUND_HALF_UP
from typing import List
from sqlalchemy import and_
from models.batch import Batch
from models.daily_batch import DailyBatch
from database import SessionLocal

def increment_age(batch_id: int):
    db = SessionLocal()
    try:
        db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not db_batch:
            return None
        with localcontext() as ctx:
            ctx.prec = 4
            ctx.rounding = ROUND_HALF_UP
            age = Decimal(db_batch.age)
            if age % 1 < 0.7:
                db_batch.age = str(age + Decimal('0.1'))
            elif age % 1 == 0.7:
                db_batch.age = str(age + Decimal('0.4'))
            else:
                raise Exception('Invalid age')
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error incrementing age at {datetime.now()}: {e}")
    finally:
        db.close()

def update_opening_count(batch_id: int):
    db = SessionLocal()
    try:
        db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not db_batch:
            return None
        db_batch.opening_count = db_batch.closing_count
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error updating opening count at {datetime.now()}: {e}")
    finally:
        db.close()

def update_batch_stats(batch_id: int):
    """
    Reset mortality, culls, table_eggs, jumbo, cr, total_eggs, and hd to zero for a given batch.
    """
    db = SessionLocal()
    try:
        db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not db_batch:
            return None
        db_batch.mortality = 0
        db_batch.culls = 0
        db_batch.table = 0
        db_batch.jumbo = 0
        db_batch.cr = 0
        db_batch.total_eggs = 0
        db_batch.HD = 0
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error resetting batch stats at {datetime.now()}: {e}")
    finally:
        db.close()

def run_eod_tasks():
    db = SessionLocal()
    try:
        print(f"Running EOD tasks at {datetime.now()}...")
        batches = db.query(Batch).all()
        batch_date = datetime.now().date()

        for batch in batches:
            exists = db.query(DailyBatch).filter(
                and_(
                    DailyBatch.batch_no == batch.batch_no,
                    DailyBatch.batch_date == batch_date
                )
            ).first()

            if exists:
                print(f"Skipping batch {batch.id}, DailyBatch already exists.")
                continue

            daily = DailyBatch(
                batch_id=batch.id,
                batch_date=batch_date,
                shed_no=batch.shed_no,
                batch_no=batch.batch_no,
                age=batch.age,
                opening_count=batch.opening_count,
                mortality=batch.mortality,
                culls=batch.culls,
                closing_count=batch.closing_count,
                table=batch.table,
                jumbo=batch.jumbo,
                cr=batch.cr,
                HD=batch.HD
            )
            db.add(daily)
            increment_age(batch.id)
            update_opening_count(batch.id)
            update_batch_stats(batch.id)

        db.commit()
        print(f"EOD tasks completed at {datetime.now()}")
    except Exception as e:
        db.rollback()
        print(f"Error in EOD tasks: {e}")
    finally:
        db.close()
