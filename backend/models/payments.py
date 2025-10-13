from sqlalchemy import Column, Integer, Numeric, Date, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base # Assuming Base is imported from your database setup
from models.audit_mixin import AuditMixin

class Payment(Base, AuditMixin):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    payment_date = Column(Date, nullable=False)
    amount_paid = Column(Numeric(10, 3), nullable=False) # Increased precision
    payment_mode = Column(String, nullable=True) # e.g., "Cash", "Bank Transfer", "Cheque"
    reference_number = Column(String, nullable=True) # Cheque number, transaction ID etc.
    notes = Column(Text, nullable=True)
    payment_receipt = Column(String(500), nullable=True)
    tenant_id = Column(String, index=True)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="payments")