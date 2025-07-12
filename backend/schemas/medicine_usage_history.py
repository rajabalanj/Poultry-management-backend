# backend/schemas/medicine_usage_history.py

from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

class MedicineUsageHistoryBase(BaseModel):
    medicine_id: int
    used_quantity_grams: Decimal # Always expect input in grams for usage
    batch_id: int
    used_at: Optional[datetime] = None
    changed_by: Optional[str] = None

class MedicineUsageHistoryCreate(MedicineUsageHistoryBase):
    pass

class MedicineUsageHistory(MedicineUsageHistoryBase):
    id: int
    # Optional fields for response to provide more context
    medicine_name: Optional[str] = None
    shed_no: Optional[str] = None

    class Config:
        from_attributes = True