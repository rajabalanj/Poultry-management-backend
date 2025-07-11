from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import pytz

class MedicineAudit(Base):
    __tablename__ = "medicine_audit"

    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicine.id"), nullable=False)
    # change_type = Column(String, nullable=False)  # "manual" or "composition"
    change_amount = Column(Float, nullable=False) # Positive or negative
    # change_amount_unit = Column(String, nullable=False)
    old_weight = Column(Float, nullable=False)
    # old_weight_unit = Column(String, nullable=False)
    # new_weight_unit = Column(String, nullable=False)
    new_weight = Column(Float, nullable=False)
    changed_by = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.now(pytz.timezone('Asia/Kolkata')))
    note = Column(String, nullable=True)

    medicine = relationship("Medicine", back_populates="audits")