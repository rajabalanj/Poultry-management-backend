from pydantic import BaseModel

class CompositionUsageItemBase(BaseModel):
    inventory_item_id: int
    weight: float
    item_name: str
    item_category: str

class CompositionUsageItemCreate(CompositionUsageItemBase):
    pass

class CompositionUsageItem(CompositionUsageItemBase):
    id: int
    usage_history_id: int

    class Config:
        from_attributes = True
