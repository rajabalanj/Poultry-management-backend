from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
from database import Base
from models.audit_mixin import TimestampMixin
import pytz

class Batch(Base, TimestampMixin):
    __tablename__ = "batch"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    batch_no = Column(String)
    date = Column(Date, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')).date())
    age = Column(Numeric(4, 1))
    opening_count = Column(Integer)
    daily_batches = relationship("DailyBatch", back_populates="batch")
    closing_date = Column(Date, nullable=True)

    @hybrid_property
    def is_active(self):
        return self.closing_date is None or self.closing_date > datetime.now(pytz.timezone('Asia/Kolkata')).date()

    @is_active.expression
    def is_active(cls):
        return cls.closing_date.is_(None) | (cls.closing_date > datetime.now(pytz.timezone('Asia/Kolkata')).date())
    # standard_hen_day_percentage = Column(Numeric(5, 2), default=0.0, nullable=True)  # Percentage of hen days
    
    @hybrid_property
    def batch_type(self):
        if self.age < 8:
            return 'Chick'
        elif self.age <= 17:
            return 'Grower'
        elif self.age > 17:
            return 'Layer'

    @batch_type.expression
    def batch_type(cls):
        from sqlalchemy import case
        return case(
            (cls.age < 8, 'Chick'),
            (cls.age <= 17, 'Grower'),
            else_='Layer'
        )
