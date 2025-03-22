from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from database import Base

class BatchHistory(Base):
    __tablename__ = "batch_history"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batch.id"))
    batch_no = Column(String)
    action = Column(String)
    changed_by = Column(String, nullable=True)
    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    additional_info = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now()) 