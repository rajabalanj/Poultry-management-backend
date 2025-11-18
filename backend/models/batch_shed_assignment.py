from sqlalchemy import Column, Integer, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
from models.audit_mixin import TimestampMixin

class BatchShedAssignment(Base, TimestampMixin):
    __tablename__ = "batch_shed_assignments"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("batch.id"), nullable=False)
    shed_id = Column(Integer, ForeignKey("sheds.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)

    batch = relationship("Batch")
    shed = relationship("Shed")

    __table_args__ = (
        UniqueConstraint('batch_id', 'shed_id', 'start_date', name='unique_batch_shed_assignment'),
    )
