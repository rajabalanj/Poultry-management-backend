from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class InventoryItemAuditBase(BaseModel):
    inventory_item_id: int
    change_type: str
    change_amount: float
    old_quantity: float
    new_quantity: float
    changed_by: Optional[str] = None
    note: Optional[str] = None

class InventoryItemAuditCreate(InventoryItemAuditBase):
    pass

class InventoryItemAudit(InventoryItemAuditBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True
