from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base
from models.audit_mixin import AuditMixin

class FinancialSettings(Base, AuditMixin):
    __tablename__ = "financial_settings"

    tenant_id = Column(String, primary_key=True, index=True)
    is_initialized = Column(Boolean, default=False, nullable=False)
    
    # Default Accounts
    default_cash_account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=True)
    default_sales_account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=True)
    default_inventory_account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=True)
    default_cogs_account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=True)
    default_operational_expense_account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=True)
    default_accounts_payable_account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=True)
    default_accounts_receivable_account_id = Column(Integer, ForeignKey("chart_of_accounts.id"), nullable=True)

    # Relationships
    default_cash_account = relationship("ChartOfAccounts", foreign_keys=[default_cash_account_id])
    default_sales_account = relationship("ChartOfAccounts", foreign_keys=[default_sales_account_id])
    default_inventory_account = relationship("ChartOfAccounts", foreign_keys=[default_inventory_account_id])
    default_cogs_account = relationship("ChartOfAccounts", foreign_keys=[default_cogs_account_id])
    default_operational_expense_account = relationship("ChartOfAccounts", foreign_keys=[default_operational_expense_account_id])
    default_accounts_payable_account = relationship("ChartOfAccounts", foreign_keys=[default_accounts_payable_account_id])
    default_accounts_receivable_account = relationship("ChartOfAccounts", foreign_keys=[default_accounts_receivable_account_id])