
from sqlalchemy import Column, Integer, String, Text, Boolean, UniqueConstraint
from database import Base
from models.audit_mixin import AuditMixin

class ChartOfAccounts(Base, AuditMixin):
    __tablename__ = "chart_of_accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_code = Column(String(20), nullable=False, index=True)
    account_name = Column(String(100), nullable=False)
    account_type = Column(String(20), nullable=False)  # Asset, Liability, Equity, Revenue, Expense
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    tenant_id = Column(String, index=True)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'account_code', name='_tenant_account_code_uc'),
    )
