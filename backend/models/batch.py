from sqlalchemy import Column, Integer, String, Date, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import relationship
from database import Base
from datetime import date

class Batch(Base):
    __tablename__ = "batch"

    id = Column(Integer, primary_key=True, index=True)
    shed_no = Column(String, unique=True)
    batch_no = Column(String, unique=True)
    date = Column(Date, default=date.today)
    age = Column(String)  # Format: "week.day" (e.g., "1.1" for 8 days)
    opening_count = Column(Integer)
    mortality = Column(Integer, default=0)
    culls = Column(Integer, default=0)
    closing_count = Column(Integer)
    table_eggs = Column(Integer, default=0)
    jumbo = Column(Integer, default=0)
    cr = Column(Integer, default=0)
    hd =  Column('hd', Numeric(11, 9), default=0)
    is_chick_batch = Column(Boolean, default=False)
    daily_batches = relationship("DailyBatch", back_populates="batch") 