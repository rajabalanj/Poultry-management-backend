from sqlalchemy import Column, Integer, String, DateTime, Numeric, UniqueConstraint
from database import Base
from datetime import datetime
import pytz
from models.audit_mixin import AuditMixin

class OperationalExpense(Base, AuditMixin):
    __tablename__ = 'operational_expenses'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String, index=True)
    date = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')).date())
    expense_type = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'date', 'expense_type', name='_tenant_date_expense_uc'),
    )
