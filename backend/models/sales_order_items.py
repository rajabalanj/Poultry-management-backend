from sqlalchemy import Column, Integer, Numeric, ForeignKey, String, CheckConstraint
from sqlalchemy.orm import relationship
from database import Base

class SalesOrderItem(Base):
    __tablename__ = "sales_order_items"

    id = Column(Integer, primary_key=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=True)
    composition_id = Column(Integer, ForeignKey("composition.id"), nullable=True)
    quantity = Column(Numeric(10, 3), nullable=False)
    price_per_unit = Column(Numeric(10, 3), nullable=False)
    line_total = Column(Numeric(10, 3), nullable=False)
    tenant_id = Column(String, index=True)
    variant_id = Column(Integer, ForeignKey("inventory_item_variants.id"), nullable=True)
    variant_name = Column(String, nullable=True)

    # Relationships
    sales_order = relationship("SalesOrder", back_populates="items")
    inventory_item = relationship("InventoryItem")
    composition = relationship("Composition")
    variant = relationship("InventoryItemVariant")

    __table_args__ = (
        CheckConstraint(
            '(inventory_item_id IS NOT NULL AND composition_id IS NULL) OR (inventory_item_id IS NULL AND composition_id IS NOT NULL)',
            name='check_item_or_composition'
        ),
    )