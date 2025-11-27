import logging
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import SessionLocal
from models.egg_room_reports import EggRoomReport
from models.daily_batch import DailyBatch
from crud import app_config as crud_app_config

logger = logging.getLogger(__name__)

def propagate_egg_room_updates(start_date: date, tenant_id: str):
    """
    Recalculates and propagates changes for egg room reports from a given start date.

    This task should be run in the background whenever a change in daily_batch
    or an earlier egg_room_report could affect subsequent reports.

    Args:
        start_date: The date from which to start the propagation.
        tenant_id: The tenant for whom the propagation should run.
    """
    logger.info(f"Starting egg room report propagation for tenant '{tenant_id}' from {start_date}.")
    db: Session = SessionLocal()
    try:
        today = date.today()
        if start_date > today:
            logger.warning(f"Propagation start date {start_date} is in the future. Aborting.")
            return

        # Get all potentially affected reports in one query
        reports_in_range = db.query(EggRoomReport).filter(
            EggRoomReport.report_date >= start_date,
            EggRoomReport.tenant_id == tenant_id
        ).order_by(EggRoomReport.report_date).all()
        
        report_map = {report.report_date: report for report in reports_in_range}
        
        current_date = start_date
        # Loop until the day after today to ensure today's report is processed
        while current_date <= today:
            # Get the most recent previous report to find the correct opening balance.
            # This needs to be the most up-to-date version, so we query it inside the loop.
            prev_report = db.query(EggRoomReport).filter(
                EggRoomReport.report_date < current_date,
                EggRoomReport.tenant_id == tenant_id
            ).order_by(EggRoomReport.report_date.desc()).first()

            if prev_report:
                table_opening_correct = prev_report.table_closing
                jumbo_opening_correct = prev_report.jumbo_closing
                grade_c_opening_correct = prev_report.grade_c_closing
            else: # This is the first day of the cascade, get opening from app_config.
                table_opening_config = crud_app_config.get_config(db, tenant_id, name="table_opening")
                jumbo_opening_config = crud_app_config.get_config(db, tenant_id, name="jumbo_opening")
                grade_c_opening_config = crud_app_config.get_config(db, tenant_id, name="grade_c_opening")
                table_opening_correct = int(table_opening_config.value) if table_opening_config else 0
                jumbo_opening_correct = int(jumbo_opening_config.value) if jumbo_opening_config else 0
                grade_c_opening_correct = int(grade_c_opening_config.value) if grade_c_opening_config else 0

            # Get the report for the current day from our prefetched map
            report_to_update = report_map.get(current_date)
            
            if not report_to_update:
                # If a report for a day in the middle doesn't exist, we can't propagate through it.
                # The daily GET or a manual creation should handle this gap.
                logger.warning(f"No egg room report found for {current_date} to propagate updates. Stopping cascade.")
                break # Stop the cascade if there's a gap.

            # Recalculate received amounts from daily_batch for the current day
            daily_batch_sums = db.query(
                func.sum(DailyBatch.table_eggs).label("table_received"),
                func.sum(DailyBatch.jumbo).label("jumbo_received"),
                func.sum(DailyBatch.cr).label("grade_c_shed_received")
            ).filter(
                DailyBatch.batch_date == current_date,
                DailyBatch.tenant_id == tenant_id
            ).first()

            # Update the report object in the session with the correct values
            report_to_update.table_opening = table_opening_correct
            report_to_update.jumbo_opening = jumbo_opening_correct
            report_to_update.grade_c_opening = grade_c_opening_correct
            report_to_update.table_received = daily_batch_sums.table_received or 0
            report_to_update.jumbo_received = daily_batch_sums.jumbo_received or 0
            report_to_update.grade_c_shed_received = daily_batch_sums.grade_c_shed_received or 0
            
            logger.debug(f"Updating report for {current_date}. New opening: {table_opening_correct}, New received: {report_to_update.table_received}. New closing will be {report_to_update.table_closing}")
            
            current_date += timedelta(days=1)

        db.commit()
        logger.info(f"Successfully propagated egg room updates for tenant '{tenant_id}' from {start_date}.")
    except Exception as e:
        logger.error(f"Error during egg room propagation task: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
