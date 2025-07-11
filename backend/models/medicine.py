from sqlalchemy import Column, Integer, Numeric, String, Date
from sqlalchemy.orm import relationship
from database import Base
from datetime import date

class Medicine(Base):
    __tablename__ = "medicine"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True)
    quantity = Column(Numeric(8, 3))
    unit = Column(String)  # e.g., "kg", "tons"
    createdDate = Column(Date, default=date.today)
    # Add new columns for warning thresholds
    warningGramThreshold = Column(Numeric(10, 3), nullable=True)
    warningKGThreshold = Column(Numeric(10, 3), nullable=True)
    audits = relationship("MedicineAudit", back_populates="medicine")