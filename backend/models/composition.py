from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base
from models.audit_mixin import AuditMixin

class Composition(Base, AuditMixin):
    __tablename__ = "composition"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    tenant_id = Column(String, index=True)
    inventory_items = relationship("InventoryItemInComposition", cascade="all, delete-orphan", backref="composition")