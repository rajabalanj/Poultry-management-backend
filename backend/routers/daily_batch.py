from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List
from datetime import date
import pandas as pd
import io
import logging

from database import get_db
from models.batch import Batch as BatchModel
from models.daily_batch import DailyBatch as DailyBatchModel
from schemas.daily_batch import DailyBatchCreate, DailyBatchUpdate
import crud.daily_batch as crud_daily_batch
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict
from utils.auth_utils import get_current_user, get_user_identifier
from utils.tenancy import get_tenant_id

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/daily-batch/upload-excel/")
def upload_daily_batch_excel(file: UploadFile = File(...), db: Session = Depends(get_db), user: dict = Depends(get_current_user), tenant_id: str = Depends(get_tenant_id)):
    """
    Upload and process an Excel file for daily batch data.
    This function processes multiple daily reports within a single Excel file,
    updates existing records, and recalculates subsequent records.
    """
    try:
        contents = file.file.read()
        df = pd.read_excel(io.BytesIO(contents), header=None)

        all_batches = db.query(BatchModel).filter(BatchModel.tenant_id == tenant_id).all()
        batch_map = {b.batch_no: b for b in all_batches}

        date_indices = df.index[df[0] == 'DATE'].tolist()
        if not date_indices:
            raise HTTPException(status_code=400, detail="No 'DATE' rows found in the Excel file.")

        processed_records_count = 0
        
        excel_data = []
        for i, date_idx in enumerate(date_indices):
            report_date_str = df.iloc[date_idx, 1]
            try:
                report_date = pd.to_datetime(report_date_str, format='%m-%d-%Y').date()
            except ValueError:
                try:
                    report_date = pd.to_datetime(report_date_str, format='%d/%m/%Y').date()
                except ValueError:
                    logger.error(f"Could not parse date '{report_date_str}' at row {date_idx}. Skipping this report section.")
                    continue

            data_start = date_idx + 2
            if i + 1 < len(date_indices):
                data_end = date_indices[i + 1]
            else:
                total_rows_after_start = df.index[(df[0] == 'TOTAL') & (df.index >= data_start)].tolist()
                if total_rows_after_start:
                    data_end = total_rows_after_start[-1]
                else:
                    data_end = len(df)

            for row_idx in range(data_start, data_end):
                row = df.iloc[row_idx]
                if pd.isna(row[0]) or str(row[0]).strip().upper() in ['TOTAL', 'GROWER', 'CHICK']:
                    continue
                excel_data.append({'report_date': report_date, 'row': row, 'row_idx': row_idx})

        excel_data.sort(key=lambda x: x['report_date'])

        for data in excel_data:
            report_date = data['report_date']
            row = data['row']
            row_idx = data['row_idx']

            try:
                int(row[0]) # Validate batch_id is integer
            except (ValueError, TypeError):
                logger.warning(f"Skipping row {row_idx} (Date: {report_date}) due to non-integer batch ID: '{row[0]}'.")
                continue

            if pd.isna(row[1]) or pd.isna(row[2]) or pd.isna(row[3]):
                logger.warning(f"Skipping row {row_idx} (Date: {report_date}) due to missing essential data: {row.tolist()}")
                continue

            batch_no_excel = str(row[1]).strip()
            if batch_no_excel not in batch_map:
                logger.warning(f"Skipping row {row_idx} (Date: {report_date}) due to batch_no not found in batch table: '{batch_no_excel}'.")
                continue

            batch_obj = batch_map[batch_no_excel]
            batch_id_for_daily_batch = batch_obj.id

            if report_date < batch_obj.date:
                logger.warning(f"Skipping row {row_idx} (Date: {report_date}) for batch '{batch_no_excel}' because it's before the batch start date ({batch_obj.date}).")
                continue

            from utils.age_utils import calculate_age_progression
            prev_daily = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id_for_daily_batch,
                DailyBatchModel.batch_date < report_date
            ).order_by(DailyBatchModel.batch_date.desc()).first()

            if prev_daily:
                opening_count = prev_daily.closing_count
                try:
                    prev_age = float(prev_daily.age)
                except (ValueError, TypeError):
                    prev_age = 0.0
                days_diff = (report_date - prev_daily.batch_date.date()).days
                age = calculate_age_progression(prev_age, days_diff)
            else:
                opening_count = batch_obj.opening_count
                try:
                    base_age = float(batch_obj.age)
                except (ValueError, TypeError):
                    base_age = 0.0
                days_diff = (report_date - batch_obj.date).days
                age = calculate_age_progression(base_age, days_diff)

            existing_daily_batch = crud_daily_batch.get_batch(db, batch_id_for_daily_batch, report_date, tenant_id)

            mortality_excel = int(row[4]) if pd.notna(row[4]) else 0
            culls_excel = int(row[5]) if pd.notna(row[5]) else 0
            table_eggs_excel = int(row[7]) if pd.notna(row[7]) else 0
            jumbo_excel = int(row[8]) if pd.notna(row[8]) else 0
            cr_excel = int(row[9]) if pd.notna(row[9]) else 0

            if existing_daily_batch:
                # Audit: capture old values then update
                try:
                    old_values = sqlalchemy_to_dict(existing_daily_batch)
                except Exception:
                    old_values = None

                existing_daily_batch.opening_count = opening_count
                existing_daily_batch.age = str(round(age, 1))
                existing_daily_batch.mortality = mortality_excel
                existing_daily_batch.culls = culls_excel
                existing_daily_batch.table_eggs = table_eggs_excel
                existing_daily_batch.jumbo = jumbo_excel
                existing_daily_batch.cr = cr_excel
                db.commit()
                db.refresh(existing_daily_batch)

                # Create audit log for update
                try:
                    new_values = sqlalchemy_to_dict(existing_daily_batch)
                    log_entry = AuditLogCreate(
                        table_name='daily_batch',
                        record_id=f"{existing_daily_batch.batch_id}_{existing_daily_batch.batch_date}",
                        changed_by=get_user_identifier(user),
                        action='UPDATE',
                        old_values=old_values or {},
                        new_values=new_values or {}
                    )
                    create_audit_log(db=db, log_entry=log_entry)
                except Exception:
                    pass
            else:
                daily_batch_instance = DailyBatchCreate(
                    batch_id=batch_id_for_daily_batch,
                    tenant_id=tenant_id,
                    shed_no=batch_obj.shed_no,
                    batch_no=batch_no_excel,
                    upload_date=date.today(),
                    batch_date=report_date,
                    age=str(round(age, 1)),
                    opening_count=opening_count,
                    mortality=mortality_excel,
                    culls=culls_excel,
                    table_eggs=table_eggs_excel,
                    jumbo=jumbo_excel,
                    cr=cr_excel,
                )
                created = crud_daily_batch.create_daily_batch(db=db, daily_batch_data=daily_batch_instance, tenant_id=tenant_id)
                # Audit log for create
                try:
                    new_values = sqlalchemy_to_dict(created)
                    log_entry = AuditLogCreate(
                        table_name='daily_batch',
                        record_id=f"{created.batch_id}_{created.batch_date}",
                        changed_by=get_user_identifier(user),
                        action='CREATE',
                        old_values={},
                        new_values=new_values or {}
                    )
                    create_audit_log(db=db, log_entry=log_entry)
                except Exception:
                    pass

            processed_records_count += 1
            
            subsequent_rows = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch_id_for_daily_batch,
                DailyBatchModel.batch_date > report_date,
                DailyBatchModel.tenant_id == tenant_id
            ).order_by(DailyBatchModel.batch_date.asc()).all()

            current_record = crud_daily_batch.get_batch(db, batch_id_for_daily_batch, report_date, tenant_id)

            prev_closing = current_record.closing_count
            prev_date = current_record.batch_date
            try:
                prev_age = float(current_record.age)
            except (ValueError, TypeError):
                prev_age = 0.0

            for row_to_update in subsequent_rows:
                row_to_update.opening_count = prev_closing
                
                days_diff = (row_to_update.batch_date.date() - prev_date.date()).days
                prev_age = calculate_age_progression(prev_age, days_diff)
                row_to_update.age = str(round(prev_age, 1))
                
                prev_closing = row_to_update.closing_count
                prev_date = row_to_update.batch_date

            db.commit()

        return {"message": f"File '{file.filename}' processed. {processed_records_count} daily batch records created or updated."}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception(f"Unhandled error during Excel upload: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")
    
@router.patch("/daily-batch/{batch_id}/{batch_date}", response_model=DailyBatchUpdate)
def update_daily_batch(
    batch_id: int,
    batch_date: str,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Update a daily batch row by batch_id and batch_date. Applies propagation logic for age, counts."""
    from models.daily_batch import DailyBatch as DailyBatchModel
    from sqlalchemy import and_
    import dateutil.parser
    from crud.audit_log import create_audit_log
    from schemas.audit_log import AuditLogCreate
    from utils import sqlalchemy_to_dict

    # Parse date string
    try:
        batch_date_obj = dateutil.parser.parse(batch_date).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid batch_date format")

    # Fetch the current row
    daily_batch = db.query(DailyBatchModel).filter(
        and_(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date == batch_date_obj,
            DailyBatchModel.tenant_id == tenant_id
        )
    ).first()

    if not daily_batch:
        raise HTTPException(status_code=404, detail="Daily batch not found")

    old_values = sqlalchemy_to_dict(daily_batch)

    # Update fields on the current daily_batch from payload
    if "age" in payload:
        try:
            from utils import calculate_age_progression
            new_age = float(payload["age"])
            daily_batch.age = str(round(new_age, 1))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid age value")
    
    if "mortality" in payload:
        daily_batch.mortality = payload["mortality"]
    if "culls" in payload:
        daily_batch.culls = payload["culls"]
    if "opening_count" in payload:
        daily_batch.opening_count = payload["opening_count"]

    # Update simple fields (no propagation)
    for key in ("table_eggs", "cr", "jumbo"):
        if key in payload:
            setattr(daily_batch, key, payload[key])

    # Update other allowed fields dynamically
    excluded_fields = {"shed_no", "age", "mortality", "culls", "opening_count", "table_eggs", "cr", "jumbo", "closing_count", "total_eggs", "hd", "standard_hen_day_percentage"}
    for key, value in payload.items():
        if key not in excluded_fields and hasattr(daily_batch, key):
            setattr(daily_batch, key, value)

    # Propagation logic if any of the relevant fields were in the payload
    if any(key in payload for key in ["age", "mortality", "culls", "opening_count"]):
        subsequent_rows = db.query(DailyBatchModel).filter(
            DailyBatchModel.batch_id == batch_id,
            DailyBatchModel.batch_date > daily_batch.batch_date,
            DailyBatchModel.tenant_id == tenant_id
        ).order_by(DailyBatchModel.batch_date.asc()).all()

        prev_closing = daily_batch.closing_count
        prev_date = daily_batch.batch_date
        try:
            prev_age = float(daily_batch.age)
        except (ValueError, TypeError):
            prev_age = 0.0
        
        from utils import calculate_age_progression

        for row in subsequent_rows:
            # Propagate opening_count based on previous closing_count
            row.opening_count = prev_closing
            
            # Propagate age
            days_diff = (row.batch_date.date() - prev_date.date()).days
            prev_age = calculate_age_progression(prev_age, days_diff)
            row.age = str(prev_age)
            
            # Update for next iteration
            prev_closing = row.closing_count
            prev_date = row.batch_date

    new_values = sqlalchemy_to_dict(daily_batch)
    log_entry = AuditLogCreate(
        table_name='daily_batch',
        record_id=f"{batch_id}_{batch_date}",
        changed_by=get_user_identifier(user),
        action='UPDATE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)

    db.commit()
    db.refresh(daily_batch)
    return daily_batch

@router.post("/daily-batch/", response_model=List[dict])
def create_or_get_daily_batches(
    batch_date: str = Query(..., description="Date for which to fetch daily batches"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Fetch all daily_batch rows for a given batch_date.
    If a daily_batch row for an active batch does not exist for the given date, it is generated.
    If the batch_date is before a batch's start date, a message is returned for that batch.
    """
    from models.daily_batch import DailyBatch as DailyBatchModel
    from models.batch import Batch as BatchModel
    from utils import calculate_age_progression
    from dateutil import parser

    # Handle timezone format issues (+ becomes space in URL decoding)
    batch_date_str = batch_date.replace(' ', '+')
    try:
        batch_date = parser.parse(batch_date_str).date()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid batch_date format")

    today = date.today()

    # Get all active batches for the tenant, ordered by batch_no
    active_batches = db.query(BatchModel).filter(
        BatchModel.is_active,
        BatchModel.tenant_id == tenant_id
    ).order_by(BatchModel.batch_no).all()

    # Get existing daily batches for the given date and tenant, and map them by batch_id
    existing_daily_batches = db.query(DailyBatchModel).join(BatchModel).filter(
        DailyBatchModel.batch_date == batch_date,
        BatchModel.tenant_id == tenant_id,
        BatchModel.is_active
    ).all()
    existing_daily_batches_map = {db.batch_id: db for db in existing_daily_batches}

    result_list = []

    for batch in active_batches:
        if batch.id in existing_daily_batches_map:
            # Use existing daily batch
            daily = existing_daily_batches_map[batch.id]
            d = {c.name: getattr(daily, c.name) for c in daily.__table__.columns}
            d['closing_count'] = daily.closing_count
            d['hd'] = daily.hd
            d['total_eggs'] = daily.total_eggs
            d['batch_type'] = daily.batch_type
            d['standard_hen_day_percentage'] = daily.standard_hen_day_percentage
            d['feed_in_kg'] = daily.feed_in_kg
            d['standard_feed_in_kg'] = daily.standard_feed_in_kg * daily.opening_count if daily.standard_feed_in_kg and daily.opening_count else 0
            result_list.append(d)
        else:
            # Generate missing daily batch
            if batch_date < batch.date.date():
                result_list.append({
                    "batch_id": batch.id,
                    "shed_no": batch.shed_no,
                    "batch_no": batch.batch_no,
                    "message": "Please modify batch start date in configuration screen to create batch for this date.",
                    "batch_start_date": batch.date.isoformat(),
                    "requested_date": batch_date.isoformat()
                })
                continue

            # Find the most recent previous daily_batch for this batch
            prev_daily = db.query(DailyBatchModel).filter(
                DailyBatchModel.batch_id == batch.id,
                DailyBatchModel.batch_date < batch_date
            ).order_by(DailyBatchModel.batch_date.desc()).first()

            if prev_daily:
                opening_count = prev_daily.closing_count
                try:
                    prev_age = float(prev_daily.age)
                except (ValueError, TypeError):
                    prev_age = 0.0
                days_diff = (batch_date - prev_daily.batch_date.date()).days
                age = calculate_age_progression(prev_age, days_diff)
            else:
                opening_count = batch.opening_count
                try:
                    base_age = float(batch.age)
                except (ValueError, TypeError):
                    base_age = 0.0
                days_diff = (batch_date - batch.date.date()).days
                age = calculate_age_progression(base_age, days_diff)

            db_daily = DailyBatchModel(
                batch_id=batch.id,
                tenant_id=tenant_id,
                shed_no=batch.shed_no,
                batch_no=batch.batch_no,
                upload_date=today,
                batch_date=batch_date,
                age=str(round(age, 1)),
                opening_count=opening_count,
                mortality=0,
                culls=0,
                table_eggs=0,
                jumbo=0,
                cr=0,
            )
            db.add(db_daily)
            db.commit()
            db.refresh(db_daily)

            # Audit log for created daily_batch
            try:
                new_values = sqlalchemy_to_dict(db_daily)
                log_entry = AuditLogCreate(
                    table_name='daily_batch',
                    record_id=f"{db_daily.batch_id}_{db_daily.batch_date}",
                    changed_by=get_user_identifier(user),
                    action='CREATE',
                    old_values={},
                    new_values=new_values or {}
                )
                create_audit_log(db=db, log_entry=log_entry)
            except Exception:
                pass

            d = {c.name: getattr(db_daily, c.name) for c in db_daily.__table__.columns}
            d['closing_count'] = db_daily.closing_count
            d['hd'] = db_daily.hd
            d['total_eggs'] = db_daily.total_eggs
            d['batch_type'] = db_daily.batch_type
            d['standard_hen_day_percentage'] = db_daily.standard_hen_day_percentage
            d['feed_in_kg'] = db_daily.feed_in_kg
            d['standard_feed_in_kg'] = db_daily.standard_feed_in_kg * db_daily.opening_count if db_daily.standard_feed_in_kg and db_daily.opening_count else 0
            result_list.append(d)

    result_list.sort(key=lambda x: x.get('batch_no', float('inf')))

    return result_list