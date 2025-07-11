from pydantic import BaseModel
from datetime import date
from typing import Optional # Import Optional

class MedicineBase(BaseModel):
    title: str
    quantity: int
    unit: str
    createdDate: date
    # Add new optional warning threshold fields
    warningGramThreshold: Optional[float] = None
    warningKGThreshold: Optional[float] = None

class Medicine(MedicineBase):
    pass