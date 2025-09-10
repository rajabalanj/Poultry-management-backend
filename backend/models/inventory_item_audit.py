from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import pytz

class InventoryItemAudit(Base):
    __tablename__ = "inventory_item_audit"

    id = Column(Integer, primary_key=True, index=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    change_type = Column(String, nullable=False)  # "manual", "composition", "usage" etc.
    change_amount = Column(Float, nullable=False) # Positive or negative
    old_quantity = Column(Float, nullable=False)
    new_quantity = Column(Float, nullable=False)
    changed_by = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.now(pytz.timezone('Asia/Kolkata')))
    note = Column(String, nullable=True)

    inventory_item = relationship("InventoryItem", back_populates="audits")