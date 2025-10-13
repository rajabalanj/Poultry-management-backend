from sqlalchemy import Column, Integer, String, Text, Enum, Boolean
from sqlalchemy.orm import relationship
from database import Base
import enum
from models.audit_mixin import AuditMixin

class PartnerStatus(enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    BLOCKED = "Blocked"

class BusinessPartner(Base, AuditMixin):
    __tablename__ = "business_partners"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    name = Column(String, nullable=False)
    contact_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    address = Column(Text, nullable=False)
    email = Column(String, nullable=True)
    status = Column(Enum(PartnerStatus), default=PartnerStatus.ACTIVE, nullable=False)
    is_vendor = Column(Boolean, default=True, nullable=False)
    is_customer = Column(Boolean, default=True, nullable=False)

    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor", foreign_keys="PurchaseOrder.vendor_id")
    sales_orders = relationship("SalesOrder", back_populates="customer", foreign_keys="SalesOrder.customer_id")
