from sqlalchemy import Column, Integer, String, Text, Numeric, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base # Assuming Base is imported from your database setup
import enum

class PurchaseOrderStatus(enum.Enum):
    DRAFT = "Draft"
    PENDING_APPROVAL = "Pending Approval"
    APPROVED = "Approved"
    ORDERED = "Ordered"
    PARTIALLY_PAID = "Partially Paid"
    PAID = "Paid"
    CANCELLED = "Cancelled"

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, unique=True, nullable=False) # Human-readable PO number
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False)
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date, nullable=True)
    total_amount = Column(Numeric(10, 3), default=0.0, nullable=False) # Increased precision
    status = Column(Enum(PurchaseOrderStatus), default=PurchaseOrderStatus.DRAFT, nullable=False)
    notes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True) # Assuming a user ID string or name for auditing
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    vendor = relationship("Vendor", back_populates="purchase_orders")
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="purchase_order", cascade="all, delete-orphan")