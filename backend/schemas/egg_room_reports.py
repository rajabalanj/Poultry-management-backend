from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional


class EggRoomReportBase(BaseModel):
    table_damage: Optional[int] = None
    table_out: Optional[int] = None

    grade_c_labour: Optional[int] = None
    grade_c_waste: Optional[int] = None

    jumbo_waste: Optional[int] = None
    jumbo_out: Optional[int] = None
    
    model_config = {"extra": "ignore"}


class EggRoomReportCreate(EggRoomReportBase):
    report_date: date


class EggRoomReportUpdate(BaseModel):
    table_damage: Optional[int] = None
    table_out: Optional[int] = None

    grade_c_labour: Optional[int] = None
    grade_c_waste: Optional[int] = None

    jumbo_waste: Optional[int] = None
    jumbo_out: Optional[int] = None

    model_config = {"extra": "ignore"}


class EggRoomReportResponse(EggRoomReportBase):
    report_date: date
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    tenant_id: str

    table_received: Optional[int] = None
    table_transfer: Optional[int] = None
    grade_c_shed_received: Optional[int] = None
    grade_c_transfer: Optional[int] = None
    jumbo_received: Optional[int] = None
    jumbo_transfer: Optional[int] = None

    table_opening: Optional[int] = None
    table_closing: Optional[int] = None
    jumbo_opening: Optional[int] = None
    jumbo_closing: Optional[int] = None
    grade_c_opening: Optional[int] = None
    grade_c_closing: Optional[int] = None
    
    model_config = {"from_attributes": True, "extra": "ignore"}