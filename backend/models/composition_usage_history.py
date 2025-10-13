from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, JSON
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import pytz
from models.batch import Batch

class CompositionUsageHistory(Base):
    __tablename__ = "composition_usage_history"
    id = Column(Integer, primary_key=True, index=True)
    composition_id = Column(Integer, ForeignKey("composition.id"), nullable=False)
    composition_name = Column(String, nullable=False)  # Snapshot of composition name
    composition_items = Column(JSON, nullable=False)  # Snapshot of items and quantities
    times = Column(Integer, nullable=False)
    used_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    composition = relationship("Composition")
    batch_id = Column(Integer, ForeignKey("batch.id"), nullable=False)  # New column for batch_id
    batch = relationship("Batch")  # Establish a relationship with the Batch model
    tenant_id = Column(String, index=True)
