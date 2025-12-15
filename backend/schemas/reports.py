from pydantic import BaseModel
from typing import List

class InventoryValue(BaseModel):
    total_inventory_value: float

class TopSellingItem(BaseModel):
    item_id: int
    name: str
    total_quantity_sold: float

    class Config:
        # This is the correct Pydantic v2 attribute. If you are using v1, it's 'orm_mode = True'
        from_attributes = True

class TopSellingItemsReport(BaseModel):
    report_data: List[TopSellingItem]

class CompositionUsage(BaseModel):
    composition_name: str
    total_usage: float
    unit: str

class CompositionUsageReport(BaseModel):
    report: List[CompositionUsage]

