from sqlalchemy import Column, Integer, Numeric, Date, DateTime, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class SalesPayment(Base):
    __tablename__ = "sales_payments"

    id = Column(Integer, primary_key=True, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    payment_date = Column(Date, nullable=False)
    amount_paid = Column(Numeric(10, 3), nullable=False)
    payment_mode = Column(String, nullable=True)
    reference_number = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    payment_receipt = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    sales_order = relationship("SalesOrder", back_populates="payments")