from sqlalchemy import Column, Integer, String, DateTime
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
    shed_no = Column(String)
    batch_no = Column(String)
    date = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')).date())
    age = Column(String)  # Format: "week.day" (e.g., "1.1" for 8 days)
    opening_count = Column(Integer)
    daily_batches = relationship("DailyBatch", back_populates="batch")
    closing_date = Column(DateTime(timezone=True), nullable=True)

    @hybrid_property
    def is_active(self):
        return self.closing_date is None or self.closing_date > datetime.now(pytz.timezone('Asia/Kolkata')).date()

    @is_active.expression
    def is_active(cls):
        return cls.closing_date.is_(None) | (cls.closing_date > datetime.now(pytz.timezone('Asia/Kolkata')).date())
    # standard_hen_day_percentage = Column(Numeric(5, 2), default=0.0, nullable=True)  # Percentage of hen days
    
    @hybrid_property
    def batch_type(self):
        if float(self.age) < 16:
            return 'Chick'
        elif float(self.age) <= 18:  # include 18 in this range
            return 'Grower'
        elif float(self.age) > 18:
            return 'Layer'

    @batch_type.expression
    def batch_type(cls):
        from sqlalchemy import cast, Float, case
        return case(
            (cast(cls.age, Float) < 16, 'Chick'),
            (cast(cls.age, Float) <= 18, 'Grower'),
            else_='Layer'
        )
