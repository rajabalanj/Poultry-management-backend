from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class PartnerStatus(enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    BLOCKED = "Blocked"

class BusinessPartner(Base):
    __tablename__ = "business_partners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    contact_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    address = Column(Text, nullable=False)
    email = Column(String, unique=True, nullable=True)
    status = Column(Enum(PartnerStatus), default=PartnerStatus.ACTIVE, nullable=False)
    is_vendor = Column(Boolean, default=True, nullable=False)
    is_customer = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor", foreign_keys="PurchaseOrder.vendor_id")
    sales_orders = relationship("SalesOrder", back_populates="customer", foreign_keys="SalesOrder.customer_id")