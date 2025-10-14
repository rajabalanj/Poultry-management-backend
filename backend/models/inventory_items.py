from sqlalchemy import Column, Integer, String, Text, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base # Assuming Base is imported from your database setup
from models.audit_mixin import TimestampMixin

class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint('name', 'tenant_id', name='_inventory_items_name_tenant_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    name = Column(String, nullable=False)
    unit = Column(String, nullable=False) # e.g., "kg", "tons", "liters", "units"
    category = Column(String, nullable=True) # e.g., "Feed", "Medicine", "Cleaning Supplies"
    current_stock = Column(Numeric(10, 3), default=0.0, nullable=False) # Increased precision
    average_cost = Column(Numeric(10, 3), default=0.0, nullable=False) # Increased precision
    reorder_level = Column(Numeric(10, 3), nullable=True) # For general alerts
    description = Column(Text, nullable=True)

    # Relationships
    purchase_order_items = relationship("PurchaseOrderItem", back_populates="inventory_item")
    audits = relationship("InventoryItemAudit", back_populates="inventory_item")
    usage_history = relationship("InventoryItemUsageHistory", back_populates="inventory_item")
