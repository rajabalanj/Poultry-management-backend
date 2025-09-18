from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from models.business_partners import PartnerStatus

class BusinessPartnerBase(BaseModel):
    name: str
    contact_name: str
    phone: str
    address: str
    email: Optional[EmailStr] = None
    status: PartnerStatus = PartnerStatus.ACTIVE
    is_vendor: bool = True
    is_customer: bool = True

class BusinessPartnerCreate(BusinessPartnerBase):
    pass

class BusinessPartnerUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[PartnerStatus] = None
    is_vendor: Optional[bool] = None
    is_customer: Optional[bool] = None

class BusinessPartner(BusinessPartnerBase):
    id: int
    tenant_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
