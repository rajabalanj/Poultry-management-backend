from database import Base
from sqlalchemy import DECIMAL, Column, Integer, String
from models.audit_mixin import TimestampMixin

class BV300LayerPerformance(Base, TimestampMixin):
    __tablename__ = "bv300_layer_performance"

    age_weeks = Column(Integer, primary_key=True, index=True)
    mortality_cum_percent = Column(DECIMAL(5, 2), nullable=False)
    lay_percent = Column(DECIMAL(5, 2), nullable=False)
    eggs_per_bird_weekly = Column(DECIMAL(4, 2), nullable=False)
    eggs_per_bird_cum = Column(DECIMAL(6, 2), nullable=False)
    feed_intake_per_day_g = Column(Integer, nullable=False)
    feed_per_egg_g = Column(DECIMAL(6, 2), nullable=False)
    egg_weight_g = Column(DECIMAL(4, 2), nullable=False)
    body_weight_g = Column(Integer, nullable=False)
    tenant_id = Column(String, index=True)

    def __repr__(self):
        return f"<BV300LayerPerformance(age_weeks={self.age_weeks}, lay_percent={self.lay_percent})>"