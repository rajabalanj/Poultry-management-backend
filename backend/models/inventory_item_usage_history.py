from sqlalchemy import Column, Integer, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import pytz

class InventoryItemUsageHistory(Base):
    __tablename__ = "inventory_item_usage_history"
    id = Column(Integer, primary_key=True, index=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    used_quantity = Column(Numeric(10, 3), nullable=False)
    unit = Column(String, nullable=False) # e.g., "grams", "kg", "units"
    used_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    batch_id = Column(Integer, ForeignKey("batch.id"), nullable=False)
    changed_by = Column(String, nullable=True)
    tenant_id = Column(String, index=True)

    inventory_item = relationship("InventoryItem", back_populates="usage_history")
    batch = relationship("Batch")