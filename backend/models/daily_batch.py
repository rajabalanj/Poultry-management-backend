from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import date
from sqlalchemy.ext.hybrid import hybrid_property

class DailyBatch(Base):
    __tablename__ = "daily_batch"
    batch_id = Column(Integer, ForeignKey("batch.id"), primary_key=True)
    batch = relationship("Batch", back_populates="daily_batches")
    shed_no = Column(Integer)
    batch_no = Column(String)
    uploaded_date = Column(Date, default=date.today)
    batch_date = Column(Date, default=date.today, primary_key=True)
    age = Column(String)
    opening_count = Column(Integer)
    mortality = Column(Integer, default=0)
    culls = Column(Integer, default=0)
    closing_count = Column(Integer)
    table = Column(Integer, default=0)
    jumbo = Column(Integer, default=0)
    cr = Column(Integer, default=0)

    @hybrid_property
    def total_eggs(self):
        return self.table + self.jumbo + self.cr