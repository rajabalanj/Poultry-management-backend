from sqlalchemy import Column, Integer, Numeric, Date, DateTime, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base # Assuming Base is imported from your database setup

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    payment_date = Column(Date, nullable=False)
    amount_paid = Column(Numeric(10, 3), nullable=False) # Increased precision
    payment_mode = Column(String, nullable=True) # e.g., "Cash", "Bank Transfer", "Cheque"
    reference_number = Column(String, nullable=True) # Cheque number, transaction ID etc.
    notes = Column(Text, nullable=True)
    payment_receipt = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    tenant_id = Column(String, index=True)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="payments")