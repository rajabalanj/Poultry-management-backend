from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import os
from typing import Optional, Dict
from datetime import datetime, timedelta, date
from models.daily_batch import DailyBatch
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.cell_range import CellRange
from openpyxl.utils import get_column_letter
from models.bovanswhitelayerperformance import BovansWhiteLayerPerformance
from models.composition_usage_history import CompositionUsageHistory as CompositionUsageHistoryModel
from models.composition import Composition
from database import get_db
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import and_
import models
from models.batch import Batch
from utils.tenancy import get_tenant_id
from functools import lru_cache

@lru_cache()
def get_bovans_standards(db: Session, tenant_id: str) -> Dict[int, BovansWhiteLayerPerformance]:
    """
    Fetches all Bovans White Layer Performance standards for a tenant
    and returns them as a dictionary keyed by age in weeks.
    Uses lru_cache to avoid repeated database calls.
    """
    standards = db.query(BovansWhiteLayerPerformance).filter(BovansWhiteLayerPerformance.tenant_id == tenant_id).all()
    return {standard.age_weeks: standard for standard in standards}

def get_total_feed_for_day(db: Session, batch_id: int, batch_date: date, tenant_id: str) -> float:
    """
    Calculates the total feed consumed (in grams) for a specific batch on a given date.
    """
    start_of_day = datetime.combine(batch_date, datetime.min.time())
    end_of_day = datetime.combine(batch_date, datetime.max.time())

    # Get all composition usages for the batch on the given day
    usages = db.query(CompositionUsageHistoryModel).filter(
        CompositionUsageHistoryModel.batch_id == batch_id,
        CompositionUsageHistoryModel.tenant_id == tenant_id,
        CompositionUsageHistoryModel.used_at >= start_of_day,
        CompositionUsageHistoryModel.used_at <= end_of_day
    ).all()

    total_feed_grams = 0.0
    for usage in usages:
        # For each usage, get the composition
        composition = db.query(Composition).filter(Composition.id == usage.composition_id).first()
        if composition:
            # Sum the weights of all items in the composition
            total_feed_grams += sum(item.weight for item in composition.inventory_items) * usage.times
    return total_feed_grams * 1000 # Convert kg to grams

def get_daily_batches_by_date_range(db: Session, start_date: date, end_date: date, tenant_id: str):
    return db.query(models.DailyBatch).filter(
        and_(models.DailyBatch.batch_date >= start_date,
             models.DailyBatch.batch_date <= end_date,
             models.DailyBatch.tenant_id == tenant_id)
    ).all()

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)

def _calculate_summary(batches: list[DailyBatch], query_start_date: date, query_end_date: date, is_single_batch: bool):
    """Helper function to calculate summary statistics for a list of daily batches."""
    if not batches:
        return None

    summary_opening_count = 0
    summary_closing_count = 0

    if is_single_batch:
        # For a single batch, take the opening count of the first day and closing count of the last day.
        # The 'batches' list is already sorted by date.
        summary_opening_count = batches[0].opening_count
        summary_closing_count = batches[-1].closing_count
    else:
        # For multiple batches (consolidation), sum the counts on the start/end dates.
        # Calculate summary opening count: sum of opening_count for all batches on the query_start_date
        first_day_batches_for_summary = [b for b in batches if b.batch_date == query_start_date]
        summary_opening_count = sum(b.opening_count for b in first_day_batches_for_summary) if first_day_batches_for_summary else 0

        # Calculate summary closing count: sum of closing_count for all batches on the query_end_date
        last_day_batches_for_summary = [b for b in batches if b.batch_date == query_end_date]
        summary_closing_count = sum(b.closing_count for b in last_day_batches_for_summary) if last_day_batches_for_summary else 0

    # Calculate highest age across all batches and all dates in the provided list
    highest_age = 0.0
    for b in batches:
        try:
            age_val = float(b.age)
            if age_val > highest_age:
                highest_age = age_val
        except (ValueError, TypeError):
            continue # Ignore invalid age values

    # Sum totals
    total_mortality = sum(b.mortality for b in batches)
    total_culls = sum(b.culls for b in batches)
    total_table_eggs = sum(b.table_eggs for b in batches)
    total_jumbo = sum(b.jumbo for b in batches if b.jumbo is not None)
    total_cr = sum(b.cr for b in batches)
    total_eggs = total_table_eggs + total_jumbo + total_cr

    # Filter for layer batches (age >= 18 weeks) for HD calculations
    layer_batches = []
    for b in batches:
        try:
            # Only include batches that are 18 weeks or older
            if float(b.age) >= 18:
                layer_batches.append(b)
        except (ValueError, TypeError):
            # Ignore if age is not a valid number
            continue

    # Calculate averages only on layer batches
    if layer_batches:
        # Ensure hd and standard_hen_day_percentage are not None before summing
        hd_values = [b.hd for b in layer_batches if b.hd is not None]
        avg_hd = sum(hd_values) / len(hd_values) if hd_values else 0

        standard_hd_values = [float(b.standard_hen_day_percentage) for b in layer_batches if b.standard_hen_day_percentage is not None]
        avg_standard_hd = sum(standard_hd_values) / len(standard_hd_values) if standard_hd_values else 0
    else:
        avg_hd = 0
        avg_standard_hd = 0

    return {
        "opening_count": summary_opening_count,
        "mortality": total_mortality,
        "culls": total_culls,
        "closing_count": summary_closing_count,
        "table_eggs": total_table_eggs,
        "jumbo": total_jumbo,
        "cr": total_cr,
        "total_eggs": total_eggs,
        "hd": round(avg_hd, 4),
        "standard_hen_day_percentage": round(avg_standard_hd, 4),
        "highest_age": round(highest_age, 1),
    }

@router.get("/snapshot")
def get_snapshot(start_date: str, end_date: str, batch_id: Optional[int] = None, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """
    Get a snapshot of batches between the specified start_date and end_date.
    If batch_id is provided, returns all rows for that batch.
    If batch_id is not provided, consolidates data into one row per batch.
    """
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Please use YYYY-MM-DD for both start_date and end_date")

    if start_date_obj > end_date_obj:
        raise HTTPException(status_code=400, detail="Start date cannot be after the end date")

    query = db.query(DailyBatch).join(Batch).filter(
        DailyBatch.batch_date >= start_date_obj,
        DailyBatch.batch_date <= end_date_obj,
        Batch.is_active,
        Batch.tenant_id == tenant_id
    )
    
    # Fetch performance standards once
    bovans_standards = get_bovans_standards(db, tenant_id)

    summary_data = None
    detailed_result = []

    if batch_id is not None:
        query = query.filter(DailyBatch.batch_id == batch_id)
        daily_batches = query.order_by(DailyBatch.batch_date.asc()).all()
        summary_data = _calculate_summary(daily_batches, start_date_obj, end_date_obj, is_single_batch=True)

        # For a single batch, the details are the daily records
        for batch in daily_batches:
            age_weeks = 0
            try:
                age_weeks = int(float(batch.age))
            except (ValueError, TypeError):
                pass

            feed_sufficiency = "N/A"
            egg_laying_performance = "N/A"
            standard = bovans_standards.get(age_weeks)

            if standard:
                # Feed Sufficiency Calculation
                actual_feed_g = get_total_feed_for_day(db, batch.batch_id, batch.batch_date, tenant_id)
                standard_feed_g = standard.feed_intake_per_day_g * batch.opening_count
                if standard_feed_g > 0:
                    feed_sufficiency = "Sufficient" if actual_feed_g >= standard_feed_g else "Insufficient"

                # Egg Laying Performance Calculation
                if batch.hd is not None and standard.lay_percent is not None:
                    actual_hd_percent = batch.hd * 100
                    egg_laying_performance = "Met" if actual_hd_percent >= float(standard.lay_percent) else "Not Met"

            detailed_result.append({
                "batch_id": batch.batch_id,
                "batch_no": batch.batch_no,
                "batch_date": batch.batch_date.strftime("%d-%m-%Y"),
                "shed_no": batch.shed_no,
                "age": batch.age,
                "opening_count": batch.opening_count,
                "mortality": batch.mortality,
                "culls": batch.culls,
                "closing_count": batch.closing_count,
                "table_eggs": batch.table_eggs,
                "jumbo": batch.jumbo,
                "cr": batch.cr,
                "total_eggs": batch.total_eggs,
                "hd": batch.hd,
                "standard_hen_day_percentage": float(batch.standard_hen_day_percentage) if batch.standard_hen_day_percentage is not None else None,
                "feed_sufficiency": feed_sufficiency,
                "egg_laying_performance": egg_laying_performance,
            })

    else:
        # No batch_id provided, so we consolidate.
        all_daily_batches = query.order_by(DailyBatch.batch_id, DailyBatch.batch_date.asc()).all()
        
        # First, calculate the grand summary over all batches
        summary_data = _calculate_summary(all_daily_batches, start_date_obj, end_date_obj, is_single_batch=False)

        # Group batches by batch_id for detailed consolidation
        from itertools import groupby
        
        grouped_batches = groupby(all_daily_batches, key=lambda b: b.batch_id)

        for b_id, group in grouped_batches:
            batch_records = list(group)
            # Calculate a summary for this specific batch's records
            batch_summary = _calculate_summary(batch_records, batch_records[0].batch_date, batch_records[-1].batch_date, is_single_batch=True)
            
            if batch_summary:
                # Add batch-specific info to the summary
                batch_summary["batch_id"] = b_id
                batch_summary["batch_no"] = batch_records[0].batch_no
                batch_summary["shed_no"] = batch_records[0].shed_no
                detailed_result.append(batch_summary)

        detailed_result.sort(key=lambda x: x.get('batch_no', ''))

    response_content = {
        "details": detailed_result,
        "summary": summary_data
    }

    return JSONResponse(content=response_content)

def write_daily_report_excel(batches, report_date=None, file_path=None, tenant_id: str = None):
    if report_date is None:
        report_date = date.today()
    if file_path is None:
        file_path = f"daily_report_combined_{tenant_id}.xlsx" if tenant_id else "daily_report_combined.xlsx"

    report_date_str = report_date.strftime("%d-%m-%Y")
    header1 = ["DATE", report_date_str, "", "", "DAILY REPORT", "", "", "", "", "", "", "","", ""]
    # Adjust header1 to match the number of columns in header2
    header2 = ["BATCH", "SHED", "AGE", "OPEN", "MORT", "CULLS", "CLOSING", "TABLE", "JUMBO", "CR", "TOTAL", "HD%", "STD"]

    if os.path.exists(file_path):
        wb = load_workbook(file_path)
        ws = wb.active
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Daily Report"

    # Find if today's report already exists and remove it
    found_row = None
    for i in range(ws.max_row, 0, -1):  # Start from last row to first
        row = [cell.value for cell in ws[i]]
        if row and row[0] == "DATE" and row[1] == report_date_str:
            found_row = i
            break


    if found_row:
        # Remove existing block (today's DATE to TOTAL row)
        end_row = found_row
        while end_row <= ws.max_row:
            if ws.cell(row=end_row, column=1).value == "TOTAL":
                break
            end_row += 1
        ws.delete_rows(found_row, end_row - found_row + 1)

    # Append data to bottom
    # Check if the last row is empty and add a blank row for spacing
    last_row_values = [cell.value for cell in ws[ws.max_row]]
    if any(last_row_values):  # if the last row is not completely empty
        ws.append([])         # add a blank row for spacing
        start_row = ws.max_row + 2
    else:
        start_row = ws.max_row + 1

    # Now append header and data
    ws.append(header1)
    ws.append(header2)
    
    # Write batch rows
    total_open = total_mort = total_culls = total_closing = total_table = total_jumbo = total_cr = total_total = total_hd_percent_dummy = total_std_dummy = 0
    for batch in batches:
        row = [
            batch.batch_no,
            batch.shed_no,
            batch.age,
            batch.opening_count,
            batch.mortality,
            batch.culls,
            batch.closing_count,
            getattr(batch, "table_eggs", 0),
            getattr(batch, "jumbo", 0),
            getattr(batch, "cr", 0),
            getattr(batch, "total", 0),
            round(batch.closing_count / max(1, batch.opening_count), 4), # Dummy HD% calculation
            round(float(batch.age) * 2.5, 1) if batch.age else round(float(batch.age) * 2.5, 1) # Dummy STD calculation
        ]
        ws.append(row)
        total_open += batch.opening_count
        total_mort += batch.mortality
        total_culls += batch.culls
        total_closing += batch.closing_count
        total_table += getattr(batch, "table_eggs", 0)
        total_jumbo += getattr(batch, "jumbo", 0)
        total_cr += getattr(batch, "cr", 0)
        total_total += getattr(batch, "total", 0)
        # Accumulate dummy values for totals
        total_hd_percent_dummy += round(batch.closing_count / max(1, batch.opening_count), 4)
        total_std_dummy += round(float(batch.age) * 2.5, 1)
        

    # Write totals row
    ws.append([
        "TOTAL", "", 0, total_open, total_mort, total_culls, total_closing,
        total_table, total_jumbo, total_cr, total_total,
         round(total_hd_percent_dummy / len(batches) if batches else 0, 4), # Dummy average HD%
         round(total_std_dummy / len(batches) if batches else 0, 1) # Dummy average STD
    ])

    # Apply formatting
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    red_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    orange_red_fill = PatternFill(start_color="FF6600", end_color="FF6600", fill_type="solid") # Closer to the image's orange-red
    bold_font_black = Font(bold=True, color="000000") # Black font for yellow fill
    bold_font_white = Font(bold=True, color="FFFFFF") # White font for red/orange-red fill
    green_fill = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
    bold_font = Font(bold=True)

     # Formatting for header1 (DATE and DAILY REPORT)
    date_cell = ws.cell(row=start_row, column=1)
    date_cell.fill = yellow_fill
    date_cell.font = bold_font_black

    report_date_cell = ws.cell(row=start_row, column=2)
    report_date_cell.fill = yellow_fill
    report_date_cell.font = bold_font_black

    daily_report_cell = ws.cell(row=start_row, column=5) # Column E (5th column) for "DAILY REPORT"
    daily_report_cell.value = "DAILY REPORT"
    daily_report_cell.fill = red_fill
    daily_report_cell.font = bold_font_white
    # Merge cells for "DAILY REPORT"
    ws.merge_cells(start_row=start_row, start_column=5, end_row=start_row, end_column=len(header2))
    daily_report_cell.alignment = Alignment(horizontal='center', vertical='center')


    # Formatting for header2 (BATCH, SHED, etc.)
    for col_idx, cell in enumerate(ws[start_row + 1]):
        cell.fill = orange_red_fill
        cell.font = bold_font_white
        # Set column width
        ws.column_dimensions[get_column_letter(col_idx + 1)].width = 10 # Adjust width as needed

    # Formatting for Total row
    for cell in ws[ws.max_row]:
        cell.fill = yellow_fill
        cell.font = bold_font_black

    wb.save(file_path)
    return file_path