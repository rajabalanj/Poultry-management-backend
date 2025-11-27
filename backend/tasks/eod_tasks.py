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
    or an earlier egg_room_report could affect subsequent reports. This version
    handles gaps in reports by carrying over balances.

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

        # Get all potentially affected reports in one query to work with them in memory.
        reports_in_range = db.query(EggRoomReport).filter(
            EggRoomReport.report_date >= start_date,
            EggRoomReport.tenant_id == tenant_id
        ).order_by(EggRoomReport.report_date).all()
        
        report_map = {report.report_date: report for report in reports_in_range}
        
        # Determine the correct opening balance from the day *before* the cascade starts.
        prev_report = db.query(EggRoomReport).filter(
            EggRoomReport.report_date < start_date,
            EggRoomReport.tenant_id == tenant_id
        ).order_by(EggRoomReport.report_date.desc()).first()

        if prev_report:
            last_table_closing = prev_report.table_closing
            last_jumbo_closing = prev_report.jumbo_closing
            last_grade_c_closing = prev_report.grade_c_closing
        else:  # No previous report, so get opening balances from app_config.
            table_opening_config = crud_app_config.get_config(db, tenant_id, name="table_opening")
            jumbo_opening_config = crud_app_config.get_config(db, tenant_id, name="jumbo_opening")
            grade_c_opening_config = crud_app_config.get_config(db, tenant_id, name="grade_c_opening")
            last_table_closing = int(table_opening_config.value) if table_opening_config else 0
            last_jumbo_closing = int(jumbo_opening_config.value) if jumbo_opening_config else 0
            last_grade_c_closing = int(grade_c_opening_config.value) if grade_c_opening_config else 0

        current_date = start_date
        # Loop from the start date through today to process all necessary days.
        while current_date <= today:
            report_to_update = report_map.get(current_date)
            
            # Recalculate received amounts from daily_batch for the current day,
            # as these might have changed and are needed for the balance calculation.
            daily_batch_sums = db.query(
                func.sum(DailyBatch.table_eggs).label("table_received"),
                func.sum(DailyBatch.jumbo).label("jumbo_received"),
                func.sum(DailyBatch.cr).label("grade_c_shed_received")
            ).filter(
                DailyBatch.batch_date == current_date,
                DailyBatch.tenant_id == tenant_id
            ).first()

            table_received_today = daily_batch_sums.table_received or 0
            jumbo_received_today = daily_batch_sums.jumbo_received or 0
            grade_c_received_today = daily_batch_sums.grade_c_shed_received or 0

            if report_to_update:
                # An existing report is found, so we update its values.
                report_to_update.table_opening = last_table_closing
                report_to_update.jumbo_opening = last_jumbo_closing
                report_to_update.grade_c_opening = last_grade_c_closing

                # Also update received amounts in case daily_batch changed.
                report_to_update.table_received = table_received_today
                report_to_update.jumbo_received = jumbo_received_today
                report_to_update.grade_c_shed_received = grade_c_received_today
                
                # The new closing balances for this day become the opening for the next day.
                last_table_closing = report_to_update.table_closing
                last_jumbo_closing = report_to_update.jumbo_closing
                last_grade_c_closing = report_to_update.grade_c_closing
                
                logger.debug(f"Updating report for {current_date}. New opening: {report_to_update.table_opening}, New closing: {last_table_closing}")

            else:
                # No report exists for this day. We carry over the balance through the gap.
                # We assume no eggs were dispatched or moved externally, so the closing balance for
                # this "gap" day is the opening balance plus any eggs received from sheds.
                last_table_closing += table_received_today
                last_jumbo_closing += jumbo_received_today
                last_grade_c_closing += grade_c_received_today
                logger.debug(f"No report for {current_date}. Carrying over balance. New closing for gap day: {last_table_closing}")

            current_date += timedelta(days=1)

        db.commit()
        logger.info(f"Successfully propagated egg room updates for tenant '{tenant_id}' from {start_date}.")
    except Exception as e:
        logger.error(f"Error during egg room propagation task: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
