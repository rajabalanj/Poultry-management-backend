from sqlalchemy import Column, Integer, String, Text, Numeric, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum

class SalesOrderStatus(enum.Enum):
    DRAFT = "Draft"
    PENDING_APPROVAL = "Pending Approval"
    APPROVED = "Approved"
    SHIPPED = "Shipped"
    PARTIALLY_PAID = "Partially Paid"
    PAID = "Paid"
    CANCELLED = "Cancelled"

class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)  # Reusing vendors as customers
    order_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(10, 3), default=0.0, nullable=False)
    total_amount_paid = Column(Numeric(10, 3), default=0.0, server_default='0.0', nullable=False)
    status = Column(Enum(SalesOrderStatus), default=SalesOrderStatus.DRAFT, nullable=False)
    notes = Column(Text, nullable=True)
    payment_receipt = Column(String(500), nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    vendor = relationship("Vendor", back_populates="sales_orders")
    items = relationship("SalesOrderItem", back_populates="sales_order", cascade="all, delete-orphan")
    payments = relationship("SalesPayment", back_populates="sales_order", cascade="all, delete-orphan")