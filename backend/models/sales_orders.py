from sqlalchemy import Column, Integer, String, Text, Numeric, Date, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
import enum
from models.audit_mixin import AuditMixin

class SalesOrderStatus(enum.Enum):
    DRAFT = "Draft"
    APPROVED = "Approved"
    PARTIALLY_PAID = "Partially Paid"
    PAID = "Paid"

class SalesOrder(Base, AuditMixin):
    __tablename__ = "sales_orders"
    __table_args__ = (UniqueConstraint('tenant_id', 'so_number', name='_tenant_so_number_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    so_number = Column(Integer, index=True) # Tenant-specific sequential number
    bill_no = Column(String, nullable=True)
    customer_id = Column(Integer, ForeignKey("business_partners.id"), nullable=False)
    order_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(10, 3), default=0.0, nullable=False)
    total_amount_paid = Column(Numeric(10, 3), default=0.0, server_default='0.0', nullable=False)
    status = Column(Enum(SalesOrderStatus), default=SalesOrderStatus.DRAFT, nullable=False)
    notes = Column(Text, nullable=True)
    payment_receipt = Column(String(500), nullable=True)
    tenant_id = Column(String, index=True)

    # Relationships
    customer = relationship("BusinessPartner", back_populates="sales_orders", foreign_keys=[customer_id])
    items = relationship("SalesOrderItem", back_populates="sales_order", cascade="all, delete-orphan")
    payments = relationship("SalesPayment", back_populates="sales_order", cascade="all, delete-orphan")