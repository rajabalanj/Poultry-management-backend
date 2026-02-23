from pydantic import BaseModel, Field, validator
from decimal import Decimal
from typing import Optional

class JournalItemBase(BaseModel):
    account_id: int
    debit: Decimal = Field(..., ge=0, decimal_places=2)
    credit: Decimal = Field(..., ge=0, decimal_places=2)

class JournalItemCreate(JournalItemBase):
    pass

class JournalItem(JournalItemBase):
    id: int
    journal_entry_id: int

    class Config:
        from_attributes = True
