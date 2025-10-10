from pydantic import BaseModel
from typing import Optional, Dict, Any

class AuditLogCreate(BaseModel):
    table_name: str
    record_id: int
    changed_by: str
    action: str
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
