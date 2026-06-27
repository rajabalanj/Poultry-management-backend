from sqlalchemy import Column, Integer, String, DateTime, Numeric, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
import pytz
from models.audit_mixin import AuditMixin

class OperationalExpense(Base, AuditMixin):
    __tablename__ = 'operational_expenses'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    expense_date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')).date())
    account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)

    # Relationships
    account = relationship("ChartOfAccounts")
