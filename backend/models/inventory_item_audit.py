from sqlalchemy import Column, Integer, String, DateTime, Float, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import pytz

class InventoryItemAudit(Base):
    __tablename__ = "inventory_item_audit"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    change_type = Column(String, nullable=False)  # "manual", "composition", "usage" etc.
    change_amount = Column(Numeric(10, 3), nullable=False) # Positive or negative
    old_quantity = Column(Numeric(10, 3), nullable=False)
    new_quantity = Column(Numeric(10, 3), nullable=False)
    changed_by = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.now(pytz.timezone('Asia/Kolkata')))
    note = Column(String, nullable=True)

    inventory_item = relationship("InventoryItem", back_populates="audits")