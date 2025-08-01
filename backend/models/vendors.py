from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base # Assuming Base is imported from your database setup
import enum

class VendorStatus(enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    ON_HOLD = "On Hold"

class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    contact_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    address = Column(Text, nullable=False)
    email = Column(String, unique=True, nullable=True) # Made unique for better data integrity
    status = Column(Enum(VendorStatus), default=VendorStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")