from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class CompositionUsageHistory(Base):
    __tablename__ = "composition_usage_history"
    id = Column(Integer, primary_key=True, index=True)
    composition_id = Column(Integer, ForeignKey("composition.id"), nullable=False)
    times = Column(Integer, nullable=False)
    used_at = Column(DateTime, default=datetime.utcnow)
    composition = relationship("Composition")
