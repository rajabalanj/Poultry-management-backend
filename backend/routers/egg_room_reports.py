from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate, EggRoomReportResponse
from crud import egg_room_reports as egg_crud
import logging
import traceback
from fastapi.responses import JSONResponse
from models.egg_room_reports import EggRoomReport
from models.daily_batch import DailyBatch
from models.app_config import AppConfig  # Import AppConfig
from datetime import datetime, date  # Import date for comparison
from utils.auth_utils import get_current_user, get_user_identifier
from utils.tenancy import get_tenant_id

def datetime_to_iso(dt):
    """Safely convert datetime to ISO format, returning None if datetime is None"""
    return dt.isoformat() if dt else None

router = APIRouter(prefix="/egg-room-report", tags=["egg_room_reports"])
logger = logging.getLogger("egg_room_reports")


def get_system_start_date(db: Session, tenant_id: str) -> date:
    """Fetches the system start date from AppConfig."""
    start_date_config = db.query(AppConfig).filter(
        AppConfig.name == 'system_start_date', AppConfig.tenant_id == tenant_id).first()
    if not start_date_config:
        # Define a default or raise an error if not configured
        # For production, it's better to ensure this is configured
        logger.warning(
            "system_start_date not found in AppConfig. Defaulting to 2000-01-01.")
        return date(2000, 1, 1)  # A very old default if not set
    try:
        return datetime.strptime(start_date_config.value, "%Y-%m-%d").date()
    except ValueError:
        logger.error(
            f"Invalid system_start_date format in AppConfig: {start_date_config.value}. Defaulting to 2000-01-01.")
        # Fallback for malformed date
        return date(2000, 1, 1)


@router.get("/{report_date}")
def get_report(report_date: str, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id), request: Request = None):
    user = get_current_user(request) if request else {}
    user_id = get_user_identifier(user)
    try:
        requested_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        system_start_date = get_system_start_date(db, tenant_id)

        if requested_date < system_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report date {report_date} cannot be before the system start date of {system_start_date.isoformat()}."
            )

        report = egg_crud.get_report_by_date(db, report_date, tenant_id)

        # Get previous day's closing for opening balance calculation
        prev_report = db.query(EggRoomReport).filter(
            EggRoomReport.report_date < requested_date,
            EggRoomReport.tenant_id == tenant_id
        ).order_by(EggRoomReport.report_date.desc()).first()

        if not report:
            if requested_date > date.today():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot create reports for future dates ({report_date})."
                )

            dummy_data = EggRoomReportCreate(
                report_date=requested_date,
                table_transfer=0, table_damage=0, table_out=0,
                jumbo_transfer=0, jumbo_waste=0, jumbo_out=0,
                grade_c_transfer=0, grade_c_labour=0, grade_c_waste=0,
                tenant_id=tenant_id
            )
            report = egg_crud.create_report(db, dummy_data, tenant_id, user_id)
        
        # Self-healing logic: Check for and correct stale data.
        update_required = False
        
        # 1. Check and correct "received" amounts from daily_batch
        daily_batch_sums = db.query(
            func.sum(DailyBatch.table_eggs).label("table_received"),
            func.sum(DailyBatch.jumbo).label("jumbo_received"),
            func.sum(DailyBatch.cr).label("grade_c_shed_received")
        ).filter(
            DailyBatch.batch_date == requested_date,
            DailyBatch.tenant_id == tenant_id
        ).first()

        if report.table_received != (daily_batch_sums.table_received or 0):
            report.table_received = daily_batch_sums.table_received or 0
            update_required = True

        if report.jumbo_received != (daily_batch_sums.jumbo_received or 0):
            report.jumbo_received = daily_batch_sums.jumbo_received or 0
            update_required = True

        if report.grade_c_shed_received != (daily_batch_sums.grade_c_shed_received or 0):
            report.grade_c_shed_received = daily_batch_sums.grade_c_shed_received or 0
            update_required = True

        # 2. Check and correct "opening" amounts
        if prev_report:
            if (report.table_opening != prev_report.table_closing or
                report.jumbo_opening != prev_report.jumbo_closing or
                report.grade_c_opening != prev_report.grade_c_closing):
                report.table_opening = prev_report.table_closing
                report.jumbo_opening = prev_report.jumbo_closing
                report.grade_c_opening = prev_report.grade_c_closing
                update_required = True
        else: # If no previous report, check against app_config
            table_opening_config = db.query(AppConfig).filter(AppConfig.name == 'table_opening', AppConfig.tenant_id == tenant_id).first()
            jumbo_opening_config = db.query(AppConfig).filter(AppConfig.name == 'jumbo_opening', AppConfig.tenant_id == tenant_id).first()
            grade_c_opening_config = db.query(AppConfig).filter(AppConfig.name == 'grade_c_opening', AppConfig.tenant_id == tenant_id).first()

            table_opening = int(table_opening_config.value) if table_opening_config else 0
            jumbo_opening = int(jumbo_opening_config.value) if jumbo_opening_config else 0
            grade_c_opening = int(grade_c_opening_config.value) if grade_c_opening_config else 0

            if (report.table_opening != table_opening or
                report.jumbo_opening != jumbo_opening or
                report.grade_c_opening != grade_c_opening):
                report.table_opening = table_opening
                report.jumbo_opening = jumbo_opening
                report.grade_c_opening = grade_c_opening
                update_required = True

        # 3. If any data was corrected, commit and then get a fresh object
        if update_required:
            db.commit()
            # Re-fetch the report to ensure all calculated properties are re-evaluated
            # based on the now-corrected data.
            report = egg_crud.get_report_by_date(db, report_date, tenant_id)

        # 4. Serialize the final, correct report for the response
        if report:
            result = {
                "report_date": report.report_date.isoformat(),
                "table_received": report.table_received,
                "table_transfer": report.table_transfer,
                "table_damage": report.table_damage,
                "table_out": report.table_out,
                "table_in": report.table_in,
                "grade_c_shed_received": report.grade_c_shed_received,
                "grade_c_room_received": report.grade_c_room_received,
                "grade_c_transfer": report.grade_c_transfer,
                "grade_c_labour": report.grade_c_labour,
                "grade_c_waste": report.grade_c_waste,
                "jumbo_received": report.jumbo_received,
                "jumbo_transfer": report.jumbo_transfer,
                "jumbo_waste": report.jumbo_waste,
                "jumbo_in": report.jumbo_in,
                "jumbo_out": report.jumbo_out,
                "created_at": datetime_to_iso(report.created_at),
                "updated_at": datetime_to_iso(report.updated_at),
                "table_opening": report.table_opening,
                "table_closing": report.table_closing,
                "jumbo_opening": report.jumbo_opening,
                "jumbo_closing": report.jumbo_closing,
                "grade_c_opening": report.grade_c_opening,
                "grade_c_closing": report.grade_c_closing,
            }
            for key, value in result.items():
                if key not in ['report_date', 'created_at', 'updated_at']:
                    if value is None or value == '':
                        result[key] = 0
            return JSONResponse(content=result)
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not found after creation/update attempt")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching egg room report for {report_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/", response_model=EggRoomReportResponse)
def create_report(report: EggRoomReportCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user), tenant_id: str = Depends(get_tenant_id)):
    try:
        requested_date = report.report_date  # Already a date object from Pydantic
        system_start_date = get_system_start_date(db, tenant_id)

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
        existing_report = egg_crud.get_report_by_date(
            db, requested_date.isoformat(), tenant_id)
        if existing_report:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Report for date {requested_date.isoformat()} already exists. Use PUT to update."
            )

        report.table_transfer = 0
        report.jumbo_transfer = 0
        report.grade_c_transfer = 0
        
        created_report = egg_crud.create_report(db, report, tenant_id, get_user_identifier(current_user))
        if created_report:
            # ... (rest of your serialization logic remains the same) ...
            result = {
                "report_date": created_report.report_date.isoformat(),
                "table_received": created_report.table_received,
                "table_transfer": created_report.table_transfer,
                "table_damage": created_report.table_damage,
                "table_out": created_report.table_out,
                "table_in": created_report.table_in,
                "grade_c_shed_received": created_report.grade_c_shed_received,
                "grade_c_room_received": created_report.grade_c_room_received,
                "grade_c_transfer": created_report.grade_c_transfer,
                "grade_c_labour": created_report.grade_c_labour,
                "grade_c_waste": created_report.grade_c_waste,
                "jumbo_received": created_report.jumbo_received,
                "jumbo_transfer": created_report.jumbo_transfer,
                "jumbo_waste": created_report.jumbo_waste,
                "jumbo_in": created_report.jumbo_in,
                "jumbo_out": created_report.jumbo_out,
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create report")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error creating egg room report: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.put("/{report_date}")
def update_report(report_date: str, report: EggRoomReportUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user), tenant_id: str = Depends(get_tenant_id)):
    try:
        requested_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        system_start_date = get_system_start_date(db, tenant_id)

        if requested_date < system_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report date {report_date} cannot be before the system start date of {system_start_date.isoformat()}"
            )
        if requested_date > date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update reports for future dates ({report_date})."
            )

        updated_report = egg_crud.update_report(
            db, report_date, report, tenant_id, get_user_identifier(current_user))
        if not updated_report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

        # Manually serialize the updated report to include hybrid properties
        result = {
            "report_date": updated_report.report_date.isoformat(),
            "table_received": updated_report.table_received,
            "table_transfer": updated_report.table_transfer,
            "table_damage": updated_report.table_damage,
            "table_out": updated_report.table_out,
            "table_in": updated_report.table_in,
            "grade_c_shed_received": updated_report.grade_c_shed_received,
            "grade_c_room_received": updated_report.grade_c_room_received,
            "grade_c_transfer": updated_report.grade_c_transfer,
            "grade_c_labour": updated_report.grade_c_labour,
            "grade_c_waste": updated_report.grade_c_waste,
            "jumbo_received": updated_report.jumbo_received,
            "jumbo_transfer": updated_report.jumbo_transfer,
            "jumbo_waste": updated_report.jumbo_waste,
            "jumbo_in": updated_report.jumbo_in,
            "jumbo_out": updated_report.jumbo_out,
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
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error updating egg room report for {report_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")






def _calculate_egg_room_summary(reports: list[EggRoomReport]):
    """Helper function to calculate summary statistics for a list of egg room reports."""
    if not reports:
        return None

    # Assuming reports are sorted by date
    first_report = reports[0]
    last_report = reports[-1]

    summary = {
        "table_opening": first_report.table_opening or 0,
        "jumbo_opening": first_report.jumbo_opening or 0,
        "grade_c_opening": first_report.grade_c_opening or 0,
        "table_closing": last_report.table_closing or 0,
        "jumbo_closing": last_report.jumbo_closing or 0,
        "grade_c_closing": last_report.grade_c_closing or 0,
        
        "total_table_received": sum(r.table_received or 0 for r in reports),
        "total_table_transfer": sum(r.table_transfer or 0 for r in reports),
        "total_table_damage": sum(r.table_damage or 0 for r in reports),
        "total_table_out": sum(r.table_out or 0 for r in reports),
        "total_table_in": sum(r.table_in or 0 for r in reports),

        "total_jumbo_received": sum(r.jumbo_received or 0 for r in reports),
        "total_jumbo_transfer": sum(r.jumbo_transfer or 0 for r in reports),
        "total_jumbo_waste": sum(r.jumbo_waste or 0 for r in reports),
        "total_jumbo_in": sum(r.jumbo_in or 0 for r in reports),
        "total_jumbo_out": sum(r.jumbo_out or 0 for r in reports),

        "total_grade_c_shed_received": sum(r.grade_c_shed_received or 0 for r in reports),
        "total_grade_c_room_received": sum(r.grade_c_room_received or 0 for r in reports),
        "total_grade_c_transfer": sum(r.grade_c_transfer or 0 for r in reports),
        "total_grade_c_labour": sum(r.grade_c_labour or 0 for r in reports),
        "total_grade_c_waste": sum(r.grade_c_waste or 0 for r in reports),
    }
    return summary


@router.get("/")
def get_reports(start_date: str, end_date: str, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    try:
        requested_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        requested_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        system_start_date = get_system_start_date(db, tenant_id)

        if requested_end_date < requested_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End date cannot be before start date."
            )

        if requested_start_date < system_start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Query start date {start_date} cannot be before the system start date of {system_start_date.isoformat()}."
            )

        # Fetch reports for the requested date range
        reports = egg_crud.get_reports_by_date_range(
            db, start_date, end_date, tenant_id)

        detailed_result = []
        for report in reports:
            detailed_result.append({
                "report_date": report.report_date.isoformat(),
                "table_received": report.table_received,
                "table_transfer": report.table_transfer,
                "table_damage": report.table_damage,
                "table_out": report.table_out,
                "table_in": report.table_in,
                "grade_c_shed_received": report.grade_c_shed_received,
                "grade_c_room_received": report.grade_c_room_received,
                "grade_c_transfer": report.grade_c_transfer,
                "grade_c_labour": report.grade_c_labour,
                "grade_c_waste": report.grade_c_waste,
                "jumbo_received": report.jumbo_received,
                "jumbo_transfer": report.jumbo_transfer,
                "jumbo_waste": report.jumbo_waste,
                "jumbo_in": report.jumbo_in,
                "jumbo_out": report.jumbo_out,
                "created_at": datetime_to_iso(report.created_at),
                "updated_at": datetime_to_iso(report.updated_at),
                "table_opening": report.table_opening,
                "table_closing": report.table_closing,
                "jumbo_opening": report.jumbo_opening,
                "jumbo_closing": report.jumbo_closing,
                "grade_c_opening": report.grade_c_opening,
                "grade_c_closing": report.grade_c_closing,
            })
        
        summary_data = _calculate_egg_room_summary(reports)
        
        response_content = {
            "details": detailed_result,
            "summary": summary_data
        }
        
        return JSONResponse(content=response_content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error fetching egg room reports for {start_date} to {end_date}: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
