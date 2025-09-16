from sqlalchemy import Column, Integer, String, Text, Numeric, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class SalesOrderStatus(enum.Enum):
    DRAFT = "Draft"
    APPROVED = "Approved"
    PARTIALLY_PAID = "Partially Paid"
    PAID = "Paid"

class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("business_partners.id"), nullable=False)
    order_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(10, 3), default=0.0, nullable=False)
    total_amount_paid = Column(Numeric(10, 3), default=0.0, server_default='0.0', nullable=False)
    status = Column(Enum(SalesOrderStatus), default=SalesOrderStatus.DRAFT, nullable=False)
    notes = Column(Text, nullable=True)
    payment_receipt = Column(String(500), nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    tenant_id = Column(String, index=True)

    # Relationships
    customer = relationship("BusinessPartner", back_populates="sales_orders", foreign_keys=[customer_id])
    items = relationship("SalesOrderItem", back_populates="sales_order", cascade="all, delete-orphan")
    payments = relationship("SalesPayment", back_populates="sales_order", cascade="all, delete-orphan")