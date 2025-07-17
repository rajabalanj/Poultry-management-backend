from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate, EggRoomReportResponse
from crud import egg_room_reports as egg_crud
import logging
import traceback
from typing import List
from fastapi.responses import JSONResponse
from models.egg_room_reports import EggRoomReport
from models.app_config import AppConfig # Import AppConfig
from datetime import datetime, date, timedelta # Import date for comparison

router = APIRouter(prefix="/egg-room-report", tags=["egg_room_reports"])
logger = logging.getLogger("egg_room_reports")

def get_system_start_date(db: Session) -> date:
    """Fetches the system start date from AppConfig."""
    start_date_config = db.query(AppConfig).filter(AppConfig.name == 'system_start_date').first()
    if not start_date_config:
        # Define a default or raise an error if not configured
        # For production, it's better to ensure this is configured
        logger.warning("system_start_date not found in AppConfig. Defaulting to 2000-01-01.")
        return date(2000, 1, 1) # A very old default if not set
    try:
        return datetime.strptime(start_date_config.value, "%Y-%m-%d").date()
    except ValueError:
        logger.error(f"Invalid system_start_date format in AppConfig: {start_date_config.value}. Defaulting to 2000-01-01.")
        return date(2000, 1, 1) # Fallback for malformed date

@router.get("/{report_date}")
def get_report(report_date: str, db: Session = Depends(get_db)):
    try:
        # Convert report_date string to date object for comparison
        requested_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        system_start_date = get_system_start_date(db)

        if requested_date < system_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report date {report_date} cannot be before the system start date of {system_start_date.isoformat()}."
            )

        report = egg_crud.get_report_by_date(db, report_date)

        if not report:
            # Check if previous day exists and is the start date
            previous_day = requested_date - timedelta(days=1)
            # Fetch previous day's closing data to see if it's the start date
            previous_report_exists = db.query(EggRoomReport).filter(EggRoomReport.report_date == previous_day).first()

            if requested_date > date.today(): # Don't allow creating future records
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot create reports for future dates ({report_date})."
                )

            # Additional check: If requested_date is the system_start_date
            # and no previous reports exist, it's a valid first entry.
            # Otherwise, if it's not system_start_date and previous_report_exists is None,
            # it implies a skipped day, which your current logic handles by setting opening to 0.
            # No additional check needed here for "ask user to fill..." as your current logic works for it.

            dummy_data = EggRoomReportCreate(
                report_date=requested_date, # Use the date object
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
            # ... (rest of your serialization logic remains the same) ...
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found after creation attempt")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching egg room report for {report_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.post("/", response_model=EggRoomReportResponse)
def create_report(report: EggRoomReportCreate, db: Session = Depends(get_db)):
    try:
        requested_date = report.report_date # Already a date object from Pydantic
        system_start_date = get_system_start_date(db)

        if requested_date < system_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report date {requested_date.isoformat()} cannot be before the system start date of {system_start_date.isoformat()}."
            )
        if requested_date > date.today():
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot create reports for future dates ({requested_date.isoformat()})."
            )

        # Check if a report for this date already exists to prevent duplicates via POST
        existing_report = egg_crud.get_report_by_date(db, requested_date.isoformat())
        if existing_report:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Report for date {requested_date.isoformat()} already exists. Use PUT to update."
            )

        created_report = egg_crud.create_report(db, report)
        if created_report:
            # ... (rest of your serialization logic remains the same) ...
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
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create report")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating egg room report: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.put("/{report_date}")
def update_report(report_date: str, report: EggRoomReportUpdate, db: Session = Depends(get_db)):
    try:
        requested_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        system_start_date = get_system_start_date(db)

        if requested_date < system_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report date {report_date} cannot be before the system start date of {system_start_date.isoformat()}."
            )
        if requested_date > date.today():
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update reports for future dates ({report_date})."
            )

        updated_report = egg_crud.update_report(db, report_date, report)
        if not updated_report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.delete("/{report_date}")
def delete_report(report_date: str, db: Session = Depends(get_db)):
    try:
        requested_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        system_start_date = get_system_start_date(db)

        if requested_date < system_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report date {report_date} cannot be before the system start date of {system_start_date.isoformat()}."
            )
        # Also, consider if you want to prevent deletion of records from very early dates
        # to preserve historical data.
        
        return egg_crud.delete_report(db, report_date)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting egg room report for {report_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@router.get("/")
def get_reports(start_date: str, end_date: str, db: Session = Depends(get_db)):
    try:
        requested_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        requested_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        system_start_date = get_system_start_date(db)

        if requested_end_date < requested_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date cannot be before start date."
            )

        # Ensure the query range doesn't go before the system start date
        if requested_start_date < system_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Query start date {start_date} cannot be before the system start date of {system_start_date.isoformat()}."
            )

        reports = egg_crud.get_reports_by_date_range(db, start_date, end_date)

        result = []
        for report in reports:
            result.append({
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
            })
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching egg room reports for {start_date} to {end_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")