# File: egg_room_reports - Copy - Copy.py (your main router file)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate, EggRoomReportResponse
from crud import egg_room_reports as egg_crud
import logging
import traceback
from typing import List
from fastapi.responses import JSONResponse # Import JSONResponse
from models.egg_room_reports import EggRoomReport # Import EggRoomReport model
# import pdb

router = APIRouter(prefix="/egg-room-report", tags=["egg_room_reports"])
logger = logging.getLogger("egg_room_reports")

@router.get("/{report_date}") # Removed response_model to allow manual serialization
def get_report(report_date: str, db: Session = Depends(get_db)):
    try:
        # pdb.set_trace()  # Set a breakpoint for debugging
        report = egg_crud.get_report_by_date(db, report_date)
        if not report:
            # Create a dummy entry with all zero values for *database columns*
            # Hybrid properties like table_opening should NOT be set here, they are calculated
            dummy_data = EggRoomReportCreate(
                report_date=report_date,
                table_received=0,
                table_transfer=0,
                table_damage=0,
                table_out=0,
                jumbo_received=0,
                jumbo_transfer=0,
                jumbo_waste=0,
                jumbo_in=0,
                grade_c_shed_received=0,
                grade_c_room_received=0,
                grade_c_transfer=0,
                grade_c_labour=0,
                grade_c_waste=0
            )
            report = egg_crud.create_report(db, dummy_data)
        
        # Manually serialize the report including hybrid properties
        if report:
            result = {
                "report_date": report.report_date.isoformat(),
                "table_received": report.table_received,
                "table_transfer": report.table_transfer,
                "table_damage": report.table_damage,
                "table_out": report.table_out,
                "grade_c_shed_received": report.grade_c_shed_received,
                "grade_c_room_received": report.grade_c_room_received,
                "grade_c_transfer": report.grade_c_transfer,
                "grade_c_labour": report.grade_c_labour,
                "grade_c_waste": report.grade_c_waste,
                "jumbo_received": report.jumbo_received,
                "jumbo_transfer": report.jumbo_transfer,
                "jumbo_waste": report.jumbo_waste,
                "jumbo_in": report.jumbo_in,
                "created_at": report.created_at.isoformat(),
                "updated_at": report.updated_at.isoformat(),
                "table_opening": report.table_opening,
                "table_closing": report.table_closing,
                "jumbo_opening": report.jumbo_opening,
                "jumbo_closing": report.jumbo_closing,
                "grade_c_opening": report.grade_c_opening,
                "grade_c_closing": report.grade_c_closing,
            }
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=404, detail="Report not found after creation attempt")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching egg room report for {report_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/", response_model=EggRoomReportResponse)
def create_report(report: EggRoomReportCreate, db: Session = Depends(get_db)):
    try:
        created_report = egg_crud.create_report(db, report)
        # Manually serialize the created report to include hybrid properties
        if created_report:
            result = {
                "report_date": created_report.report_date.isoformat(),
                "table_received": created_report.table_received,
                "table_transfer": created_report.table_transfer,
                "table_damage": created_report.table_damage,
                "table_out": created_report.table_out,
                "grade_c_shed_received": created_report.grade_c_shed_received,
                "grade_c_room_received": created_report.grade_c_room_received,
                "grade_c_transfer": created_report.grade_c_transfer,
                "grade_c_labour": created_report.grade_c_labour,
                "grade_c_waste": created_report.grade_c_waste,
                "jumbo_received": created_report.jumbo_received,
                "jumbo_transfer": created_report.jumbo_transfer,
                "jumbo_waste": created_report.jumbo_waste,
                "jumbo_in": created_report.jumbo_in,
                "created_at": created_report.created_at.isoformat(),
                "updated_at": created_report.updated_at.isoformat(),
                "table_opening": created_report.table_opening,
                "table_closing": created_report.table_closing,
                "jumbo_opening": created_report.jumbo_opening,
                "jumbo_closing": created_report.jumbo_closing,
                "grade_c_opening": created_report.grade_c_opening,
                "grade_c_closing": created_report.grade_c_closing,
            }
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=500, detail="Failed to create report")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating egg room report: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{report_date}") # Removed response_model
def update_report(report_date: str, report: EggRoomReportUpdate, db: Session = Depends(get_db)):
    try:
        updated_report = egg_crud.update_report(db, report_date, report)
        if not updated_report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Manually serialize the updated report to include hybrid properties
        result = {
            "report_date": updated_report.report_date.isoformat(),
            "table_received": updated_report.table_received,
            "table_transfer": updated_report.table_transfer,
            "table_damage": updated_report.table_damage,
            "table_out": updated_report.table_out,
            "grade_c_shed_received": updated_report.grade_c_shed_received,
            "grade_c_room_received": updated_report.grade_c_room_received,
            "grade_c_transfer": updated_report.grade_c_transfer,
            "grade_c_labour": updated_report.grade_c_labour,
            "grade_c_waste": updated_report.grade_c_waste,
            "jumbo_received": updated_report.jumbo_received,
            "jumbo_transfer": updated_report.jumbo_transfer,
            "jumbo_waste": updated_report.jumbo_waste,
            "jumbo_in": updated_report.jumbo_in,
            "created_at": updated_report.created_at.isoformat(),
            "updated_at": updated_report.updated_at.isoformat(),
            "table_opening": updated_report.table_opening,
            "table_closing": updated_report.table_closing,
            "jumbo_opening": updated_report.jumbo_opening,
            "jumbo_closing": updated_report.jumbo_closing,
            "grade_c_opening": updated_report.grade_c_opening,
            "grade_c_closing": updated_report.grade_c_closing,
        }
        return JSONResponse(content=result)
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

# Modified endpoint for listing reports
@router.get("/")
def get_reports(start_date: str, end_date: str, db: Session = Depends(get_db)):
    try:
        reports = egg_crud.get_reports_by_date_range(db, start_date, end_date)
        
        # Manually serialize the reports including hybrid properties
        result = []
        for report in reports:
            result.append({
                "report_date": report.report_date.isoformat(), # Convert date to ISO format string
                "table_received": report.table_received,
                "table_transfer": report.table_transfer,
                "table_damage": report.table_damage,
                "table_out": report.table_out,
                "grade_c_shed_received": report.grade_c_shed_received,
                "grade_c_room_received": report.grade_c_room_received,
                "grade_c_transfer": report.grade_c_transfer,
                "grade_c_labour": report.grade_c_labour,
                "grade_c_waste": report.grade_c_waste,
                "jumbo_received": report.jumbo_received,
                "jumbo_transfer": report.jumbo_transfer,
                "jumbo_waste": report.jumbo_waste,
                "jumbo_in": report.jumbo_in,
                "created_at": report.created_at.isoformat(), # Convert datetime to ISO format string
                "updated_at": report.updated_at.isoformat(), # Convert datetime to ISO format string
                "table_opening": report.table_opening, # Hybrid property
                "table_closing": report.table_closing, # Hybrid property
                "jumbo_opening": report.jumbo_opening, # Hybrid property
                "jumbo_closing": report.jumbo_closing, # Hybrid property
                "grade_c_opening": report.grade_c_opening, # Hybrid property
                "grade_c_closing": report.grade_c_closing, # Hybrid property
            })
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching egg room reports for {start_date} to {end_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")