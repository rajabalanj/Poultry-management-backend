from database import Base
from sqlalchemy import DECIMAL, Column, Integer, String
from models.audit_mixin import TimestampMixin

class BovansWhiteLayerPerformance(Base, TimestampMixin):
    __tablename__ = "bovanswhitelayerperformance" # Ensure this matches your table name exactly

    age_weeks = Column(Integer, primary_key=True, index=True)
    livability_percent = Column(DECIMAL(5, 2), nullable=False)
    lay_percent = Column(DECIMAL(5, 2), nullable=False)
    eggs_per_bird_cum = Column(DECIMAL(6, 2), nullable=False)
    feed_intake_per_day_g = Column(Integer, nullable=False)
    feed_intake_cum_kg = Column(DECIMAL(6, 2), nullable=False)
    body_weight_g = Column(Integer, nullable=False)
    tenant_id = Column(String, index=True)

    def __repr__(self):
        return f"<BovansPerformance(age_weeks={self.age_weeks}, livability={self.livability_percent})>"