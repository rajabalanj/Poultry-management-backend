from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from models.batch import Batch

class CompositionUsageHistory(Base):
    __tablename__ = "composition_usage_history"
    id = Column(Integer, primary_key=True, index=True)
    composition_id = Column(Integer, ForeignKey("composition.id"), nullable=False)
    times = Column(Integer, nullable=False)
    used_at = Column(DateTime, default=datetime.utcnow)
    composition = relationship("Composition")
    batch_id = Column(Integer, ForeignKey("batch.id"), nullable=False)  # New column for batch_id
    batch = relationship("Batch")  # Establish a relationship with the Batch model

