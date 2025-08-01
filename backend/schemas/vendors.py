from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from models.vendors import VendorStatus # Import the enum from your models

class VendorBase(BaseModel):
    name: str
    contact_name: str
    phone: str
    address: str
    email: Optional[EmailStr] = None # Optional, and validates email format
    status: Optional[VendorStatus] = VendorStatus.ACTIVE # Default to active

class VendorCreate(VendorBase):
    pass # Inherits all fields, can add specific create-only fields if needed

class VendorUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[VendorStatus] = None

class Vendor(VendorBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True # Was orm_mode = True in older Pydantic