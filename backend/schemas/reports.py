from pydantic import BaseModel
from typing import List

class InventoryValue(BaseModel):
    total_inventory_value: float

class TopSellingItem(BaseModel):
    item_id: int
    name: str
    total_quantity_sold: float

    class Config:
        orm_mode = True

class TopSellingItemsReport(BaseModel):
    report_data: List[TopSellingItem]

