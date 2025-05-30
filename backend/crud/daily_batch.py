from sqlalchemy.orm import Session
from sqlalchemy import func
from models.daily_batch import DailyBatch
from datetime import date

def get_batch(db: Session, batch_id: int, date: date):
    return db.query(DailyBatch).filter(DailyBatch.id == batch_id).first()

def get_all_batches(db: Session, skip: int = 0, limit: int = 100):
    return db.query(DailyBatch).offset(skip).limit(limit).all()


def update_batch_history(db: Session, batch_id: int, date: date, opening_count: int, age: float, mortality_count: int, culls_count: int, table_egg_count: int, jumbo_egg_count: int, cracked_egg_count: int, closing_count: int, hd: float):
    batch_history = DailyBatch(batch_id=batch_id, date=date, opening_count=opening_count, age=age, mortality_count=mortality_count, culls_count=culls_count, table_egg_count=table_egg_count, jumbo_egg_count=jumbo_egg_count, cracked_egg_count=cracked_egg_count, closing_count=closing_count, hd=hd)
    db.session.add(batch_history)
    db.session.commit()