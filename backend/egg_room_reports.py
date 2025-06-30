from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate, EggRoomReportResponse
from crud import egg_room_reports as egg_crud
import logging
import traceback
from typing import List

router = APIRouter(prefix="/egg-room-report", tags=["egg_room_reports"])
logger = logging.getLogger("egg_room_reports")

@router.get("/{report_date}", response_model=EggRoomReportResponse)
def get_report(report_date: str, db: Session = Depends(get_db)):
    try:
        report = egg_crud.get_report_by_date(db, report_date)
        if not report:
            # Create a dummy entry with all zero values
            dummy_data = EggRoomReportCreate(
                report_date=report_date,
                table_opening=0,
                table_received=0,
                table_transfer=0,
                table_damage=0,
                table_out=0,
                table_closing=0,
                jumbo_opening=0,
                jumbo_received=0,
                jumbo_transfer=0,
                jumbo_waste=0,
                jumbo_in=0,
                jumbo_closing=0,
                grade_c_opening=0,
                grade_c_shed_received=0,
                grade_c_room_received=0,
                grade_c_transfer=0,
                grade_c_labour=0,
                grade_c_waste=0,
                grade_c_closing=0
            )
            report = egg_crud.create_report(db, dummy_data)
        return report
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching egg room report for {report_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/", response_model=EggRoomReportResponse)
def create_report(report: EggRoomReportCreate, db: Session = Depends(get_db)):
    try:
        return egg_crud.create_report(db, report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating egg room report: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{report_date}", response_model=EggRoomReportResponse)
def update_report(report_date: str, report: EggRoomReportUpdate, db: Session = Depends(get_db)):
    try:
        return egg_crud.update_report(db, report_date, report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating egg room report for {report_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{report_date}")
def delete_report(report_date: str, db: Session = Depends(get_db)):
    try:
        return egg_crud.delete_report(db, report_date)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting egg room report for {report_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/", response_model=List[EggRoomReportResponse])
def get_reports(start_date: str, end_date: str, db: Session = Depends(get_db)):
    try:
        reports = egg_crud.get_reports_by_date_range(db, start_date, end_date)
        return reports
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching egg room reports for {start_date} to {end_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")