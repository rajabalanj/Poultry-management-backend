from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
from models.audit_mixin import TimestampMixin

class InventoryItemVariant(Base, TimestampMixin):
    __tablename__ = "inventory_item_variants"
    __table_args__ = (UniqueConstraint('name', 'item_id', 'tenant_id', name='_item_variant_name_item_tenant_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    name = Column(String, nullable=False) # e.g., "Pullet", "Grade B"
    item_id = Column(Integer, ForeignKey("inventory_items.id"), nullable=False)

    item = relationship("InventoryItem", back_populates="variants")
