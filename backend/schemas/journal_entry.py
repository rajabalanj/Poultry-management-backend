from pydantic import BaseModel, validator
from typing import List, Optional
from datetime import date
from decimal import Decimal
from .journal_item import JournalItemCreate, JournalItem

class JournalEntryBase(BaseModel):
    date: date
    description: Optional[str] = None
    reference_document: Optional[str] = None

class JournalEntryCreate(JournalEntryBase):
    items: List[JournalItemCreate]

    @validator('items')
    def check_debits_equal_credits(cls, items):
        total_debit = sum(item.debit for item in items)
        total_credit = sum(item.credit for item in items)
        if total_debit != total_credit:
            raise ValueError('The sum of debits must equal the sum of credits.')
        if total_debit == 0 and total_credit == 0:
            raise ValueError('A journal entry must have non-zero debit and credit amounts.')
        return items

class JournalEntry(JournalEntryBase):
    id: int
    tenant_id: str
    items: List[JournalItem] = []

    class Config:
        from_attributes = True
