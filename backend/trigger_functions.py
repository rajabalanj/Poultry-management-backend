from datetime import datetime
from typing import List
from sqlalchemy import and_, text
from models.batch import Batch
from models.daily_batch import DailyBatch
from database import SessionLocal
from decimal import Decimal, localcontext, ROUND_HALF_UP


#Helper function for incrementing age and updating opening count
# This function is used to retrieve all batch IDs from the database.
async def get_all_batch_ids() -> List[int]:
    """
    Retrieves all batch IDs from the database.
    """
    db = SessionLocal()
    try:
        # Use a simple query to fetch only the 'id' column from the Batch table.
        batch_ids = [batch.id for batch in db.query(Batch.id).all()]
        return batch_ids
    except Exception as e:
        print(f"Error retrieving batch IDs: {e}")
        return []  # Return an empty list in case of an error.  Important:  Don't raise here, handle in caller.
    finally:
        db.close()

def increment_age( batch_id: int, changed_by: str = None):
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
        print(f"Error during age increment at {datetime.now()} IST: {e}")
        raise
    finally:
        db.close()

def update_opening_count(batch_id: int, changed_by: str = None):
    db = SessionLocal()
    try:
        db_batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not db_batch:
            return None
        # Update the opening count to be the same as the closing count
        db_batch.opening_count = db_batch.closing_count
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error during opening count update at {datetime.now()} IST: {e}")
    finally:
        db.close()

async def run_eod_tasks():
    """
    Runs all EOD tasks sequentially.  This function is scheduled.
    """
    db = SessionLocal()
    try:
        print(f"Starting data transfer at {datetime.now()} IST.")
        # Get all batches
        batches = db.query(Batch).all()
        for batch in batches:
            batch_date = datetime.now().date()
            # Check if a DailyBatch entry with the same batch_no AND batch_date exists
            existing_entry = (
                db.query(DailyBatch)
                .filter(
                    and_(
                        DailyBatch.batch_no == batch.batch_no,
                        DailyBatch.batch_date == batch_date,
                    )
                )
                .first()
            )
            if existing_entry:
                print(
                    f"Skipping batch_id {batch.id} as a DailyBatch entry with batch_no {batch.batch_no} and batch_date {batch_date} already exists."
                )
                continue  # Skip to the next batch
            # Create a DailyBatch instance
            daily_batch_entry = DailyBatch(
                batch_id=batch.id,
                batch_date=batch_date,  # Use .date() to store only the date part
                shed_no=batch.shed_no,
                batch_no=batch.batch_no,
                age=batch.age,
                opening_count=batch.opening_count,
                mortality=batch.mortality,
                culls=batch.culls,
                closing_count=batch.closing_count,
                table=batch.table,
                jumbo=batch.jumbo,
                cr=batch.cr
            )
            print(f"Total eggs for batch {batch.batch_no}: {daily_batch_entry.total_eggs}")
            db.add(daily_batch_entry)
            increment_age(batch_id=batch.id)  # Call increment_age for each batch
            update_opening_count(
                batch_id=batch.id
            )  # Call update_opening_count for each batch
        db.commit()
        print(f"Data transfer completed successfully at {datetime.now()} IST.")
    except Exception as e:
        db.rollback()
        print(f"Error during data transfer at {datetime.now()} IST: {e}")
    finally:
        db.close()