from sqlalchemy import Column, Integer, Float, ForeignKey, String
from sqlalchemy.orm import relationship
from database import Base

class InventoryItemInComposition(Base):
    __tablename__ = "inventory_item_in_composition"
    id = Column(Integer, primary_key=True, index=True)
    composition_id = Column(Integer, ForeignKey("composition.id"))
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"))
    weight = Column(Float, nullable=False)
    tenant_id = Column(String, index=True)
    inventory_item = relationship("InventoryItem")
