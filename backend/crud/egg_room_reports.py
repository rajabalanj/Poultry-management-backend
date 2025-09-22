from sqlalchemy.orm import Session
from models.egg_room_reports import EggRoomReport
from schemas.egg_room_reports import EggRoomReportCreate, EggRoomReportUpdate
from typing import List
from models.daily_batch import DailyBatch
from sqlalchemy import func
from crud import app_config as crud_app_config # Import app_config crud
from models.app_config import AppConfig # Import AppConfig model


def get_report_by_date(db: Session, report_date: str, tenant_id: str):
    return db.query(EggRoomReport).filter(EggRoomReport.report_date == report_date, EggRoomReport.tenant_id == tenant_id).first()


def get_reports_by_date_range(db: Session, start_date: str, end_date: str, tenant_id: str) -> List[EggRoomReport]:
    return (
        db.query(EggRoomReport)
        .filter(
            EggRoomReport.report_date >= start_date,
            EggRoomReport.report_date <= end_date,
            EggRoomReport.tenant_id == tenant_id
        )
        .order_by(EggRoomReport.report_date)
        .all()
    )


def create_report(db: Session, report: EggRoomReportCreate, tenant_id: str) -> EggRoomReport:
    # Calculate opening balances from previous day's closing
    prev_report = db.query(EggRoomReport).filter(
        EggRoomReport.report_date < report.report_date,
        EggRoomReport.tenant_id == tenant_id
    ).order_by(EggRoomReport.report_date.desc()).first()

    opening_values = {
        'table_opening': prev_report.table_closing if prev_report else 0,
        'jumbo_opening': prev_report.jumbo_closing if prev_report else 0,
        'grade_c_opening': prev_report.grade_c_closing if prev_report else 0
    }

    # Calculate sums from daily_batch
    daily_batch_sums = db.query(
        func.sum(DailyBatch.table_eggs).label("table_received"),
        func.sum(DailyBatch.jumbo).label("jumbo_received"),
        func.sum(DailyBatch.cr).label("grade_c_shed_received")
    ).filter(
        DailyBatch.batch_date == report.report_date,
        DailyBatch.tenant_id == tenant_id
    ).first()

    report_data = report.dict()
    report_data['table_received'] = daily_batch_sums.table_received or 0
    report_data['jumbo_received'] = daily_batch_sums.jumbo_received or 0
    report_data['grade_c_shed_received'] = daily_batch_sums.grade_c_shed_received or 0

    db_report = EggRoomReport(
        **{**report_data, **opening_values, 'tenant_id': tenant_id})
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def update_report(db: Session, report_date: str, report: EggRoomReportUpdate, tenant_id: str) -> EggRoomReport:
    """
    Updates an existing egg room report.
    The opening/closing balances of subsequent days are updated automatically on the next read.
    """
    db_report = db.query(EggRoomReport).filter(
        EggRoomReport.report_date == report_date, EggRoomReport.tenant_id == tenant_id).first()
    if not db_report:
        return None

    # Recalculate sums from daily_batch to get the correct received amount
    daily_batch_sums = db.query(
        func.sum(DailyBatch.table_eggs).label("table_received"),
        func.sum(DailyBatch.jumbo).label("jumbo_received"),
        func.sum(DailyBatch.cr).label("grade_c_shed_received")
    ).filter(
        DailyBatch.batch_date == report_date,
        DailyBatch.tenant_id == tenant_id
    ).first()

    table_received = daily_batch_sums.table_received or 0
    jumbo_received = daily_batch_sums.jumbo_received or 0
    grade_c_shed_received = daily_batch_sums.grade_c_shed_received or 0

    report_data = report.dict(exclude_unset=True)

    # Retrieve EGG_STOCK_TOLERANCE from app_config
    # This allows for a configurable buffer for egg stock, acknowledging in-house production.
    egg_stock_tolerance_config = crud_app_config.get_config(db, tenant_id, name="EGG_STOCK_TOLERANCE")
    egg_stock_tolerance = float(egg_stock_tolerance_config.value) if egg_stock_tolerance_config else 0.0

    # Check for sufficient stock before applying updates
    new_table_damage = report_data.get('table_damage', db_report.table_damage)
    new_table_out = report_data.get('table_out', db_report.table_out)
    new_jumbo_out = report_data.get('jumbo_out', db_report.jumbo_out)

    table_consumption = (new_table_damage or 0) + (new_table_out or 0)
    table_inflow = db_report.table_opening + table_received + (new_jumbo_out or 0)

    # Apply egg_stock_tolerance to table egg validation
    if table_consumption > (table_inflow + egg_stock_tolerance):
        raise ValueError(f"Insufficient stock for Table Egg. Available: {table_inflow}, Requested: {table_consumption}. (Tolerance: {egg_stock_tolerance})")

    new_jumbo_waste = report_data.get('jumbo_waste', db_report.jumbo_waste)
    jumbo_consumption = (new_jumbo_waste or 0) + (new_jumbo_out or 0)
    jumbo_inflow = db_report.jumbo_opening + jumbo_received + (new_table_out or 0)

    # Apply egg_stock_tolerance to jumbo egg validation
    if jumbo_consumption > (jumbo_inflow + egg_stock_tolerance):
        raise ValueError(f"Insufficient stock for Jumbo Egg. Available: {jumbo_inflow}, Requested: {jumbo_consumption}. (Tolerance: {egg_stock_tolerance})")

    new_grade_c_labour = report_data.get('grade_c_labour', db_report.grade_c_labour)
    new_grade_c_waste = report_data.get('grade_c_waste', db_report.grade_c_waste)
    grade_c_consumption = (new_grade_c_labour or 0) + (new_grade_c_waste or 0)
    grade_c_inflow = db_report.grade_c_opening + grade_c_shed_received + (new_table_damage or 0)

    # Apply egg_stock_tolerance to grade c egg validation
    if grade_c_consumption > (grade_c_inflow + egg_stock_tolerance):
        raise ValueError(f"Insufficient stock for Grade C Egg. Available: {grade_c_inflow}, Requested: {grade_c_consumption}. (Tolerance: {egg_stock_tolerance})")

    for key, value in report_data.items():
        setattr(db_report, key, value)

    db_report.table_received = table_received
    db_report.jumbo_received = jumbo_received
    db_report.grade_c_shed_received = grade_c_shed_received

    db.commit()
    db.refresh(db_report)
    return db_report


def delete_report(db: Session, report_date: str, tenant_id: str):
    """
    Deletes a report for a specific date.
    """
    db_report = db.query(EggRoomReport).filter(
        EggRoomReport.report_date == report_date, EggRoomReport.tenant_id == tenant_id).first()
    if not db_report:
        return None
    db.delete(db_report)
    db.commit()
    return {"message": "Report deleted"}
