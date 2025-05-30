from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import date

class Batch(Base):
    __tablename__ = "batch"

    id = Column(Integer, primary_key=True, index=True)
    shed_no = Column(Integer)
    batch_no = Column(String, unique=True)
    date = Column(Date, default=date.today)
    age = Column(String)  # Format: "week.day" (e.g., "1.1" for 8 days)
    opening_count = Column(Integer)
    mortality = Column(Integer, default=0)
    culls = Column(Integer, default=0)
    closing_count = Column(Integer)
    table = Column(Integer, default=0)
    jumbo = Column(Integer, default=0)
    cr = Column(Integer, default=0)
    HD = Column(Integer, default=0)
    daily_batches = relationship("DailyBatch", back_populates="batch") 