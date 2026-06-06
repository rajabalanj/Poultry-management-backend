from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import Optional, List


class EggRoomReportBase(BaseModel):
    table_damage: int = 0
    table_out: int = 0

    grade_c_labour: int = 0
    grade_c_waste: int = 0

    jumbo_waste: int = 0
    jumbo_out: int = 0
    
    table_untrayed: int = 0
    grade_c_untrayed: int = 0
    jumbo_untrayed: int = 0
    
    @field_validator(
        'table_damage', 'table_out', 'grade_c_labour', 'grade_c_waste', 
        'jumbo_waste', 'jumbo_out', 'table_untrayed', 'grade_c_untrayed', 'jumbo_untrayed',
        mode='before'
    )
    @classmethod
    def replace_none_with_zero(cls, v):
        return 0 if v is None else v

    model_config = {"extra": "ignore"}


class EggRoomReportCreate(EggRoomReportBase):
    report_date: date


class EggRoomReportUpdate(BaseModel):
    table_damage: Optional[int] = None
    table_out: Optional[int] = None
    table_untrayed: Optional[int] = None

    grade_c_labour: Optional[int] = None
    grade_c_waste: Optional[int] = None
    grade_c_untrayed: Optional[int] = None

    jumbo_waste: Optional[int] = None
    jumbo_out: Optional[int] = None
    jumbo_untrayed: Optional[int] = None

    model_config = {"extra": "ignore"}


class EggRoomReportResponse(EggRoomReportBase):
    report_date: date
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    tenant_id: str

    table_received: int = 0
    table_transfer: int = 0
    grade_c_shed_received: int = 0
    grade_c_transfer: int = 0
    jumbo_received: int = 0
    jumbo_transfer: int = 0

    table_opening: int = 0
    table_closing: int = 0
    jumbo_opening: int = 0
    jumbo_closing: int = 0
    grade_c_opening: int = 0
    grade_c_closing: int = 0

    table_in: int = 0
    jumbo_in: int = 0
    grade_c_room_received: int = 0
    
    @field_validator(
        'table_received', 'table_transfer', 'grade_c_shed_received', 'grade_c_transfer',
        'jumbo_received', 'jumbo_transfer', 'table_opening', 'table_closing',
        'jumbo_opening', 'jumbo_closing', 'grade_c_opening', 'grade_c_closing',
        'table_in', 'jumbo_in', 'grade_c_room_received',
        mode='before'
    )
    @classmethod
    def replace_none_with_zero_response(cls, v):
        return 0 if v is None else v

    model_config = {"from_attributes": True, "extra": "ignore"}

class EggRoomReportSummary(BaseModel):
    table_opening: int = 0
    jumbo_opening: int = 0
    grade_c_opening: int = 0
    table_closing: int = 0
    jumbo_closing: int = 0
    grade_c_closing: int = 0
    total_table_received: int = 0
    total_table_transfer: int = 0
    total_table_damage: int = 0
    total_table_out: int = 0
    total_table_untrayed: int = 0
    total_table_in: int = 0
    total_jumbo_received: int = 0
    total_jumbo_transfer: int = 0
    total_jumbo_waste: int = 0
    total_jumbo_in: int = 0
    total_jumbo_out: int = 0
    total_jumbo_untrayed: int = 0
    total_grade_c_shed_received: int = 0
    total_grade_c_room_received: int = 0
    total_grade_c_transfer: int = 0
    total_grade_c_labour: int = 0
    total_grade_c_waste: int = 0
    total_grade_c_untrayed: int = 0

class EggRoomReportsListResponse(BaseModel):
    details: List[EggRoomReportResponse]
    summary: EggRoomReportSummary