from sqlalchemy import Column, Integer, String, Date, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
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
    daily_batches = relationship("DailyBatch", back_populates="batch")
    # status = Column(String, default="active")  # Status of the batch (e.g., active, inactive, completed)
    closing_date = Column(Date, nullable=True)

    @hybrid_property
    def is_active(self):
        return self.closing_date is None or self.closing_date > date.today()

    @is_active.expression
    def is_active(cls):
        return cls.closing_date.is_(None) | (cls.closing_date > date.today())
    # standard_hen_day_percentage = Column(Numeric(5, 2), default=0.0, nullable=True)  # Percentage of hen days
    
    @hybrid_property
    def batch_type(self):
        if float(self.age) < 16:
            return 'Chick'
        elif float(self.age) <= 18:  # include 18 in this range
            return 'Grower'
        elif float(self.age) > 18:
            return 'Layer'