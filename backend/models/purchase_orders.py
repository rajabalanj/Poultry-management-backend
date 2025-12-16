from sqlalchemy import Column, Integer, String, Text, Numeric, Date, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base # Assuming Base is imported from your database setup
import enum
from models.audit_mixin import AuditMixin

class PurchaseOrderStatus(enum.Enum):
    DRAFT = "Draft"
    APPROVED = "Approved"
    PARTIALLY_PAID = "Partially Paid"
    PAID = "Paid"

class PurchaseOrder(Base, AuditMixin):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint('tenant_id', 'po_number', name='_tenant_po_number_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(Integer, index=True) # Tenant-specific sequential number
    bill_no = Column(String, nullable=True)
    vendor_id = Column(Integer, ForeignKey("business_partners.id"), nullable=False)
    order_date = Column(Date, nullable=False)
    total_amount = Column(Numeric(10, 3), default=0.0, nullable=False) # Increased precision
    total_amount_paid = Column(Numeric(10, 3), default=0.0, server_default='0.0', nullable=False) # Total payments made
    status = Column(Enum(PurchaseOrderStatus), default=PurchaseOrderStatus.DRAFT, nullable=False)
    notes = Column(Text, nullable=True)
    payment_receipt = Column(String(500), nullable=True)
    tenant_id = Column(String, index=True)

    # Relationships
    vendor = relationship("BusinessPartner", back_populates="purchase_orders", foreign_keys=[vendor_id])
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="purchase_order", cascade="all, delete-orphan")