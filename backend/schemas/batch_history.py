from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class BatchHistoryBase(BaseModel):
    batch_id: int
    batch_no: str
    action: str
    changed_by: Optional[str] = None
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    additional_info: Optional[str] = None

class BatchHistoryCreate(BatchHistoryBase):
    pass

class BatchHistory(BatchHistoryBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True 