from sqlalchemy import Column, Integer, Numeric, ForeignKey, String
from sqlalchemy.orm import relationship
from database import Base # Assuming Base is imported from your database setup

class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False) # Increased precision
    price_per_unit = Column(Numeric(10, 3), nullable=False) # Increased precision
    line_total = Column(Numeric(10, 3), nullable=False) # quantity * price_per_unit, stored for convenience
    tenant_id = Column(String, index=True)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="items")
    inventory_item = relationship("InventoryItem", back_populates="purchase_order_items")