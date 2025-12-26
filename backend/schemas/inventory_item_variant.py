from pydantic import BaseModel
from typing import Optional

class InventoryItemVariantBase(BaseModel):
    name: str
    item_id: int

class InventoryItemVariantCreate(InventoryItemVariantBase):
    pass

class InventoryItemVariant(InventoryItemVariantBase):
    id: int
    tenant_id: str

    class Config:
        from_attributes = True
