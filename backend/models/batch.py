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
    is_chick_batch = Column(Boolean, default=False)
    daily_batches = relationship("DailyBatch", back_populates="batch")
    standard_hen_day_percentage = Column(Numeric(5, 2), default=0.0, nullable=True)  # Percentage of hen days 