from sqlalchemy import Column, Integer, Numeric, ForeignKey, CheckConstraint, String
from sqlalchemy.orm import relationship
from database import Base
from models.audit_mixin import AuditMixin

class JournalItem(Base, AuditMixin):
    __tablename__ = "journal_items"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True, nullable=False)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=False)
    debit = Column(Numeric(10, 2), CheckConstraint('debit >= 0'), nullable=False, default=0.0)
    credit = Column(Numeric(10, 2), CheckConstraint('credit >= 0'), nullable=False, default=0.0)

    # Relationships
    journal_entry = relationship("JournalEntry", back_populates="items")
    account = relationship("ChartOfAccounts")

    __table_args__ = (
        CheckConstraint(
            '(debit > 0 AND credit = 0) OR (debit = 0 AND credit > 0) OR (debit = 0 AND credit = 0)',
            name='check_debit_or_credit_exclusive'
        ),
    )
