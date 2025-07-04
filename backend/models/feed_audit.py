from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class FeedAudit(Base):
    __tablename__ = "feed_audit"

    id = Column(Integer, primary_key=True, index=True)
    feed_id = Column(Integer, ForeignKey("feed.id"), nullable=False)
    change_type = Column(String, nullable=False)  # "manual" or "composition"
    change_amount = Column(Float, nullable=False) # Positive or negative
    old_weight = Column(Float, nullable=False)
    new_weight = Column(Float, nullable=False)
    changed_by = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    note = Column(String, nullable=True)

    feed = relationship("Feed", back_populates="audits")