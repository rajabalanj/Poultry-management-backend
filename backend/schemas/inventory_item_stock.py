from pydantic import BaseModel
from datetime import date
from decimal import Decimal
from typing import Optional, List

class DailyStock(BaseModel):
    date: str
    stock: Optional[Decimal]

class DailyStockReport(BaseModel):
    data: List[DailyStock]

    class Config:
        orm_mode = True

