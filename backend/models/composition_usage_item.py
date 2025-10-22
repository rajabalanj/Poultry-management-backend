from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from database import Base
from models.inventory_items import InventoryItem

class CompositionUsageItem(Base):
    __tablename__ = "composition_usage_item"
    id = Column(Integer, primary_key=True, index=True)
    usage_history_id = Column(Integer, ForeignKey("composition_usage_history.id"), nullable=False)
    inventory_item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)
    weight = Column(Float, nullable=False)
    item_name = Column(String) # Snapshot for historical accuracy
    item_category = Column(String) # Snapshot for historical accuracy

    usage_history = relationship("CompositionUsageHistory", back_populates="items")
    inventory_item = relationship("InventoryItem")
