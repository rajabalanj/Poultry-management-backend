from sqlalchemy import Column, Integer, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship
from database import Base # Assuming 'database' module is at the same level as 'models'
from datetime import datetime

class MedicineUsageHistory(Base):
    __tablename__ = "medicine_usage_history"
    id = Column(Integer, primary_key=True, index=True)
    medicine_id = Column(Integer, ForeignKey("medicine.id"), nullable=False)
    # The quantity used in grams (base unit for tracking usage)
    used_quantity_grams = Column(Numeric(10, 3), nullable=False)
    used_at = Column(DateTime, default=datetime.utcnow)
    batch_id = Column(Integer, ForeignKey("batch.id"), nullable=False) # Link to batch/shed_no
    changed_by = Column(String, nullable=True) # Who performed the action

    medicine = relationship("Medicine")
    batch = relationship("Batch")