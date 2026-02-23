from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.orm import relationship
from database import Base
from models.audit_mixin import AuditMixin

class JournalEntry(Base, AuditMixin):
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=True)
    reference_document = Column(String, nullable=True)

    # Relationships
    items = relationship("JournalItem", back_populates="journal_entry", cascade="all, delete-orphan")
