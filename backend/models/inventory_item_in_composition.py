from sqlalchemy import Column, Integer, ForeignKey, String, Numeric
from sqlalchemy.orm import relationship
from database import Base

class InventoryItemInComposition(Base):
    __tablename__ = "inventory_item_in_composition"
    id = Column(Integer, primary_key=True, index=True)
    composition_id = Column(Integer, ForeignKey("composition.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    weight = Column(Numeric(10, 3), nullable=False)
    wastage_percentage = Column(Numeric(5, 2), nullable=True)
    tenant_id = Column(String, index=True)
    inventory_item = relationship("InventoryItem")
