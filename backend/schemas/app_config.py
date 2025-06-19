from pydantic import BaseModel
from typing import Optional

class AppConfigBase(BaseModel):
    lowKgThreshold: float
    lowTonThreshold: float
    # Add more config fields as needed

class AppConfigCreate(AppConfigBase):
    pass

class AppConfigUpdate(BaseModel):
    lowKgThreshold: Optional[float] = None
    lowTonThreshold: Optional[float] = None
    # Add more config fields as needed

class AppConfigOut(AppConfigBase):
    id: int

    class Config:
        from_attributes = True