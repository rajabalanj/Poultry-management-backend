from pydantic import BaseModel
from datetime import date
from typing import Optional # Import Optional

class FeedBase(BaseModel):
    title: str
    quantity: int
    unit: str
    createdDate: date
    # Add new optional warning threshold fields
    warningKgThreshold: Optional[float] = None
    warningTonThreshold: Optional[float] = None

class Feed(FeedBase):
    pass