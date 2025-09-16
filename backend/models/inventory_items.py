from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base # Assuming Base is imported from your database setup

class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    name = Column(String, nullable=False)
    unit = Column(String, nullable=False) # e.g., "kg", "tons", "liters", "units"
    category = Column(String, nullable=True) # e.g., "Feed", "Medicine", "Cleaning Supplies"
    current_stock = Column(Numeric(10, 3), default=0.0, nullable=False) # Increased precision
    average_cost = Column(Numeric(10, 3), default=0.0, nullable=False) # Increased precision
    reorder_level = Column(Numeric(10, 3), nullable=True) # For general alerts
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    purchase_order_items = relationship("PurchaseOrderItem", back_populates="inventory_item")
    audits = relationship("InventoryItemAudit", back_populates="inventory_item")
    usage_history = relationship("InventoryItemUsageHistory", back_populates="inventory_item")
