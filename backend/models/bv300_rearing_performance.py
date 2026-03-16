from database import Base
from sqlalchemy import DECIMAL, Column, Integer, String
from models.audit_mixin import TimestampMixin

class BV300RearingPerformance(Base, TimestampMixin):
    __tablename__ = "bv300_rearing_performance"

    age_weeks = Column(Integer, primary_key=True, index=True)
    livability_percent = Column(DECIMAL(5, 2), nullable=False)
    body_weight_g = Column(Integer, nullable=False)
    weekly_weight_gain_g = Column(Integer, nullable=False)
    feed_intake_per_day_g = Column(Integer, nullable=False)
    feed_intake_cum_g = Column(Integer, nullable=False)
    feed_type = Column(String(50), nullable=True)
    tenant_id = Column(String, index=True)

    def __repr__(self):
        return f"<BV300RearingPerformance(age_weeks={self.age_weeks}, livability={self.livability_percent})>"