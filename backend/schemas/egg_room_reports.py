from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class EggRoomReportBase(BaseModel):
    table_opening: Optional[int]
    table_received: Optional[int]
    table_transfer: Optional[int]
    table_damage: Optional[int]
    table_out: Optional[int]
    table_closing: Optional[int]

    grade_c_opening: Optional[int]
    grade_c_shed_received: Optional[int]
    grade_c_room_received: Optional[int]
    grade_c_transfer: Optional[int]
    grade_c_labour: Optional[int]
    grade_c_waste: Optional[int]
    grade_c_closing: Optional[int]

    jumbo_opening: Optional[int]
    jumbo_received: Optional[int]
    jumbo_transfer: Optional[int]
    jumbo_waste: Optional[int]
    jumbo_in: Optional[int]
    jumbo_closing: Optional[int]

class EggRoomReportCreate(EggRoomReportBase):
    report_date: date

class EggRoomReportUpdate(EggRoomReportBase):
    pass

class EggRoomReportResponse(EggRoomReportBase):
    report_date: date
    created_at: datetime
    updated_at: datetime

    class Config:
        form_attributes = True