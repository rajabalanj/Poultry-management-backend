from sqlalchemy import Column, Integer, String, Date, Numeric, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class OperationalExpense(Base):
    __tablename__ = 'operational_expenses'

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    date = Column(Date, nullable=False)
    expense_type = Column(String, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)

    tenant = relationship("Tenant")

    __table_args__ = (
        UniqueConstraint('tenant_id', 'date', 'expense_type', name='_tenant_date_expense_uc'),
    )
