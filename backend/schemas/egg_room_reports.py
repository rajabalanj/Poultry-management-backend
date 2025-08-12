from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class EggRoomReportBase(BaseModel):
    table_received: Optional[int]
    table_transfer: Optional[int]
    table_damage: Optional[int]
    table_out: Optional[int]

    grade_c_shed_received: Optional[int]
    grade_c_transfer: Optional[int]
    grade_c_labour: Optional[int]
    grade_c_waste: Optional[int]

    jumbo_received: Optional[int]
    jumbo_transfer: Optional[int]
    jumbo_waste: Optional[int]
    jumbo_out: Optional[int]

class EggRoomReportCreate(EggRoomReportBase):
    report_date: date

class EggRoomReportUpdate(EggRoomReportBase):
    table_opening: Optional[int] = None
    jumbo_opening: Optional[int] = None
    grade_c_opening: Optional[int] = None

class EggRoomReportResponse(EggRoomReportBase):
    report_date: date
    created_at: datetime
    updated_at: datetime

    table_opening: Optional[int]
    table_closing: Optional[int]
    jumbo_opening: Optional[int]
    jumbo_closing: Optional[int]
    grade_c_opening: Optional[int]
    grade_c_closing: Optional[int]

    class Config:
        from_attributes = True # This is the correct Pydantic v2 attribute. If you are using v1, it's 'orm_mode = True'