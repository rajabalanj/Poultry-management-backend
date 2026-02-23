from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from typing import List, Optional
import logging
from datetime import date, datetime
from decimal import Decimal
import os
import uuid
from utils.auth_utils import get_current_user, get_user_identifier
from utils.tenancy import get_tenant_id
from utils.receipt_utils import generate_sales_order_receipt
import pytz
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict
from pydantic import BaseModel

try:
    from utils.s3_utils import generate_presigned_upload_url, generate_presigned_download_url
except ImportError:
    generate_presigned_upload_url = None
    generate_presigned_download_url = None

from database import get_db
from models.sales_orders import SalesOrder as SalesOrderModel, SalesOrderStatus
from models.sales_order_items import SalesOrderItem as SalesOrderItemModel
from models.inventory_items import InventoryItem as InventoryItemModel
from models.business_partners import BusinessPartner as BusinessPartnerModel
from models.inventory_item_audit import InventoryItemAudit
from models.egg_room_reports import EggRoomReport as EggRoomReportModel
from crud import app_config as crud_app_config # Import app_config crud
from crud import egg_room_reports as crud_egg_room_reports # Import egg_room_reports crud
from schemas.sales_orders import (
    SalesOrder as SalesOrderSchema,
    SalesOrderCreate,
    SalesOrderUpdate
)
from schemas.sales_order_items import SalesOrderItemCreateRequest, SalesOrderItemUpdate
from schemas.egg_room_reports import EggRoomReportCreate

# Imports for Journal Entry
from crud import journal_entry as journal_entry_crud
from schemas.journal_entry import JournalEntryCreate
from schemas.journal_item import JournalItemCreate
from crud.financial_settings import get_financial_settings

# Define egg item names constant
EGG_ITEM_NAMES = ["Table Egg", "Jumbo Egg", "Grade C Egg"]

router = APIRouter(prefix="/sales-orders", tags=["Sales Orders"])
logger = logging.getLogger("sales_orders")

@router.post("/", response_model=SalesOrderSchema, status_code=status.HTTP_201_CREATED)
def create_sales_order(
    so: SalesOrderCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Create a new sales order with associated items."""
    db_customer = db.query(BusinessPartnerModel).filter(
        BusinessPartnerModel.id == so.customer_id, 
        BusinessPartnerModel.tenant_id == tenant_id,
        BusinessPartnerModel.status == 'ACTIVE',
        BusinessPartnerModel.is_customer
    ).first()
    if not db_customer:
        raise HTTPException(status_code=400, detail="Business partner not found, inactive, or not a customer.")

    total_amount = Decimal(0)
    total_cost_of_goods = Decimal(0)
    db_so_items = []

    if not so.items:
        raise HTTPException(status_code=400, detail="Sales order must contain at least one item.")

    for item_data in so.items:
        db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_data.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
        if not db_inventory_item:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_data.inventory_item_id} not found.")
        
        # --- Stock validation logic --- 
        if db_inventory_item.name in EGG_ITEM_NAMES:
            available_stock = _get_available_egg_stock(db, tenant_id, so.order_date, db_inventory_item.name)
            if available_stock < item_data.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{db_inventory_item.name}'. Available: {available_stock}, Requested: {item_data.quantity}")
        else:
            if db_inventory_item.category != 'Supplies':
                raise HTTPException(status_code=400, detail=f"Item '{db_inventory_item.name}' cannot be sold. Only items in 'Supplies' category can be sold.")
            if db_inventory_item.current_stock is not None and db_inventory_item.current_stock < item_data.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{db_inventory_item.name}'. Available: {db_inventory_item.current_stock}, Requested: {item_data.quantity}")
        # --- End stock validation logic --- 
        
        # Price is now optional at creation. Default to 0 if not provided.
        price_per_unit = item_data.price_per_unit if item_data.price_per_unit is not None else Decimal("0.0")
        
        line_total = item_data.quantity * price_per_unit
        total_amount += line_total

        # Calculate line cost based on item type
        if db_inventory_item.name in EGG_ITEM_NAMES:
            # For eggs, don't include cost here as it's tracked through composition usage
            line_cost = Decimal(0)
        else:
            # For other items, use average cost
            line_cost = item_data.quantity * (db_inventory_item.average_cost or Decimal(0))
        total_cost_of_goods += line_cost
        
        db_so_items.append(
            SalesOrderItemModel(
                inventory_item_id=item_data.inventory_item_id,
                quantity=item_data.quantity,
                price_per_unit=price_per_unit,
                line_total=line_total,
                tenant_id=tenant_id,
                variant_id=item_data.variant_id,
                variant_name=item_data.variant_name
            )
        )
    
    last_so_number = db.query(func.max(SalesOrderModel.so_number)).filter(SalesOrderModel.tenant_id == tenant_id).scalar() or 0
    next_so_number = last_so_number + 1

    db_so = SalesOrderModel(
        so_number=next_so_number,
        customer_id=so.customer_id,
        order_date=so.order_date,
        status=SalesOrderStatus.DRAFT, # Force status to Draft on creation
        notes=so.notes,
        total_amount=total_amount,
        created_by=get_user_identifier(user),
        tenant_id=tenant_id,
        bill_no=so.bill_no
    )
    db.add(db_so)
    db.flush()

    for item in db_so_items:
        item.sales_order_id = db_so.id
        db.add(item)
    
    # Deduct inventory immediately for each sales order item
    for item in db_so_items:
        inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
        if inv is None:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item.inventory_item_id} not found when updating stock.")
        
        # --- Stock deduction logic --- 
        if inv.name in EGG_ITEM_NAMES:
            # For eggs, stock is managed via EggRoomReport, so no deduction from InventoryItem.current_stock
            pass # Stock deduction for eggs happens in the EggRoomReport update section below
        else:
            if inv.current_stock is None or inv.current_stock < item.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{getattr(inv, 'name', item.inventory_item_id)}'. Available: {inv.current_stock}, Required: {item.quantity}")
            
            old_stock = inv.current_stock or 0
            inv.current_stock -= item.quantity
            db.add(inv)

            # Create audit record for inventory decrease (sale)
            audit = InventoryItemAudit(
                inventory_item_id=inv.id,
                change_type="sale",
                change_amount=item.quantity,
                old_quantity=old_stock,
                new_quantity=inv.current_stock,
                changed_by=get_user_identifier(user),
                note=f"Sold via SO #{db_so.id}",
                tenant_id=tenant_id
            )
            db.add(audit)
        # --- End stock deduction logic --- 
    
    db.commit()

    # Update egg room report for egg sales
    table_egg_qty = 0
    jumbo_egg_qty = 0
    grade_c_egg_qty = 0

    for item_data in so.items:
        db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_data.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
        if db_inventory_item:
            if db_inventory_item.name == "Table Egg":
                table_egg_qty += item_data.quantity
            elif db_inventory_item.name == "Jumbo Egg":
                jumbo_egg_qty += item_data.quantity
            elif db_inventory_item.name == "Grade C Egg":
                grade_c_egg_qty += item_data.quantity

    if table_egg_qty > 0 or jumbo_egg_qty > 0 or grade_c_egg_qty > 0:
        egg_room_report = db.query(EggRoomReportModel).filter(
            EggRoomReportModel.report_date == so.order_date,
            EggRoomReportModel.tenant_id == tenant_id
        ).first()

        if not egg_room_report:
            logger.info(f"No egg room report found for {so.order_date}, creating one.")
            report_create = EggRoomReportCreate(
                report_date=so.order_date,
                table_damage=0, table_out=0, grade_c_labour=0, grade_c_waste=0,
                jumbo_waste=0, jumbo_out=0
            )
            egg_room_report = crud_egg_room_reports.create_report(
                db=db, report=report_create, tenant_id=tenant_id, user_id=get_user_identifier(user)
            )

        # Use an atomic UPDATE to avoid lost updates when multiple SOs modify the same report concurrently
        db.query(EggRoomReportModel).filter(
            EggRoomReportModel.report_date == so.order_date,
            EggRoomReportModel.tenant_id == tenant_id
        ).update({
            EggRoomReportModel.table_transfer: func.coalesce(EggRoomReportModel.table_transfer, 0) + int(table_egg_qty),
            EggRoomReportModel.jumbo_transfer: func.coalesce(EggRoomReportModel.jumbo_transfer, 0) + int(jumbo_egg_qty),
            EggRoomReportModel.grade_c_transfer: func.coalesce(EggRoomReportModel.grade_c_transfer, 0) + int(grade_c_egg_qty)
        }, synchronize_session=False)
        db.commit()
        # Refresh the egg_room_report object to get the updated values
        db.refresh(egg_room_report)

    # --- Create Journal Entry for Revenue (Accrual) ---
    try:
        settings = get_financial_settings(db, tenant_id)
        if not settings.default_sales_account_id or not settings.default_accounts_receivable_account_id:
            logger.error(f"Default Sales or Accounts Receivable account not configured for tenant {tenant_id}. Revenue journal entry not created for SO {db_so.id}.")
        else:
            # Debit Accounts Receivable, Credit Sales Revenue
            # Round total_amount to 2 decimal places to match journal entry requirements
            rounded_total_amount = db_so.total_amount.quantize(Decimal('0.01'))
            
            journal_items = [
                JournalItemCreate(
                    account_id=settings.default_accounts_receivable_account_id,
                    debit=rounded_total_amount,
                    credit=Decimal('0.0')
                ),
                JournalItemCreate(
                    account_id=settings.default_sales_account_id,
                    debit=Decimal('0.0'),
                    credit=rounded_total_amount
                )
            ]
            journal_entry_schema = JournalEntryCreate(
                date=db_so.order_date,
                description=f"Invoice for Sales Order SO-{db_so.so_number}",
                reference_document=f"SO-{db_so.so_number}",
                items=journal_items
            )
            journal_entry_crud.create_journal_entry(db=db, entry=journal_entry_schema, tenant_id=tenant_id)
            logger.info(f"Revenue Journal entry created for SO {db_so.id} with amount {db_so.total_amount}")
    except Exception as e:
        logger.error(f"Failed to create Revenue journal entry for SO {db_so.id}: {e}")
    # --- End Journal Entry ---

    # --- Create Journal Entry for COGS ---
    if total_cost_of_goods > 0:
        try:
            settings = get_financial_settings(db, tenant_id)
            if not settings.default_cogs_account_id or not settings.default_inventory_account_id:
                logger.error(f"Default COGS or Inventory account not configured for tenant {tenant_id}. COGS journal entry not created for SO {db_so.id}.")
            else:
                # Debit COGS, Credit Inventory
                # Round total_cost_of_goods to 2 decimal places to match journal entry requirements
                rounded_cost_of_goods = total_cost_of_goods.quantize(Decimal('0.01'))
                
                journal_items = [
                    JournalItemCreate(
                        account_id=settings.default_cogs_account_id,
                        debit=rounded_cost_of_goods,
                        credit=Decimal('0.0')
                    ),
                    JournalItemCreate(
                        account_id=settings.default_inventory_account_id,
                        debit=Decimal('0.0'),
                        credit=rounded_cost_of_goods
                    )
                ]
                journal_entry_schema = JournalEntryCreate(
                    date=db_so.order_date,
                    description=f"COGS for Sales Order SO-{db_so.so_number}",
                    reference_document=f"SO-{db_so.so_number}",
                    items=journal_items
                )
                journal_entry_crud.create_journal_entry(db=db, entry=journal_entry_schema, tenant_id=tenant_id)
                logger.info(f"COGS Journal entry created for SO {db_so.id} with amount {total_cost_of_goods}")
        except Exception as e:
            logger.error(f"Failed to create COGS journal entry for SO {db_so.id}: {e}")
    # --- End Journal Entry ---

    db.refresh(db_so)
    
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).filter(SalesOrderModel.id == db_so.id, SalesOrderModel.tenant_id == tenant_id).first()

    logger.info(f"Sales Order (ID: {db_so.id}) created for Customer ID {db_so.customer_id} by User {get_user_identifier(user)} for tenant {tenant_id}")
    return db_so

def _get_available_egg_stock(db: Session, tenant_id: str, order_date: date, egg_type: str) -> float:
    logger.info(f"Checking available stock for {egg_type} on {order_date} for tenant {tenant_id}")
    
    # First, try to get the report for the exact date
    egg_room_report = crud_egg_room_reports.get_report_by_date(db, order_date.isoformat(), tenant_id)
    
    # If no report is found for the exact date, get the most recent one before it
    if not egg_room_report:
        logger.warning(f"No EggRoomReport found for {order_date}. Trying to find the most recent report before this date.")
        egg_room_report = db.query(EggRoomReportModel).filter(
            EggRoomReportModel.report_date < order_date,
            EggRoomReportModel.tenant_id == tenant_id
        ).order_by(EggRoomReportModel.report_date.desc()).first()

    if not egg_room_report:
        logger.warning(f"No EggRoomReport found for or before {order_date} for tenant {tenant_id}. Returning 0.0 available stock.")
        return 0.0

    available_stock = Decimal("0.0")
    if egg_type == "Table Egg":
        available_stock = Decimal(str(egg_room_report.table_closing))
        logger.info(f"Table Egg closing stock: {available_stock}")
    elif egg_type == "Jumbo Egg":
        available_stock = Decimal(str(egg_room_report.jumbo_closing))
        logger.info(f"Jumbo Egg closing stock: {available_stock}")
    elif egg_type == "Grade C Egg":
        available_stock = Decimal(str(egg_room_report.grade_c_closing))
        logger.info(f"Grade C Egg closing stock: {available_stock}")
    
    # Retrieve EGG_STOCK_TOLERANCE from app_config
    egg_stock_tolerance_config = crud_app_config.get_config(db, tenant_id, name="EGG_STOCK_TOLERANCE")
    egg_stock_tolerance = Decimal(egg_stock_tolerance_config.value) if egg_stock_tolerance_config else Decimal("0.0")

    final_available_stock = available_stock + egg_stock_tolerance
    logger.info(f"Calculated available stock for {egg_type}: {available_stock} + tolerance {egg_stock_tolerance} = {final_available_stock}")
    return float(final_available_stock)

from schemas.sales_order_reports import SalesOrderReport
from crud import sales_order_reports as crud_sales_order_reports
import pandas as pd
# Add matplotlib configuration BEFORE importing dataframe_image
import matplotlib
matplotlib.use('Agg')
from fastapi.responses import StreamingResponse
import io
from enum import Enum


class ExportFormat(str, Enum):
    excel = "excel"
    pdf = "pdf"


@router.get("/reports/detailed", response_model=List[SalesOrderReport])
def get_detailed_sales_order_report(
    skip: int = 0,
    limit: int = 100,
    customer_id: Optional[int] = None,
    status: Optional[SalesOrderStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Retrieve a detailed sales order report.
    """
    return crud_sales_order_reports.get_sales_order_report(
        db=db, 
        tenant_id=tenant_id,
        skip=skip,
        limit=limit,
        customer_id=customer_id,
        status=status,
        start_date=start_date,
        end_date=end_date
    )


@router.get("/reports/detailed/export")
def export_detailed_sales_order_report(
    format: ExportFormat,
    customer_id: Optional[int] = None,
    status: Optional[SalesOrderStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """
    Export a detailed sales order report as an Excel or Image file.
    """
    # Fetch all data without pagination for export
    report_data = crud_sales_order_reports.get_sales_order_report(
        db=db, 
        tenant_id=tenant_id,
        skip=0,
        limit=None,  # Get all records for export
        customer_id=customer_id,
        status=status,
        start_date=start_date,
        end_date=end_date
    )

    if not report_data:
        raise HTTPException(status_code=404, detail="No data available for the selected filters.")

    # Flatten the data
    flattened_data = []
    for report in report_data:
        if report.items:
            for item in report.items:
                flat_item = {
                    "SO Number": report.so_number,
                    "Bill No": report.bill_no,
                    "Customer Name": report.customer_name,
                    "Order Date": report.order_date,
                    "Item Name": item.inventory_item_name,
                    "Variant Name": item.variant_name,
                    "Quantity": item.quantity,
                    "Price Per Unit": item.price_per_unit,
                    "Line Total": item.line_total,
                    "Order Total Amount": report.total_amount,
                    "Amount Paid": report.total_amount_paid,
                    "Order Status": report.status.value,
                }
                flattened_data.append(flat_item)
        else:
            # Include orders with no items
            flat_item = {
                "SO Number": report.so_number,
                "Bill No": report.bill_no,
                "Customer Name": report.customer_name,
                "Order Date": report.order_date,
                "Item Name": None,
                "Variant Name": None,
                "Quantity": 0,
                "Price Per Unit": 0,
                "Line Total": 0,
                "Order Total Amount": report.total_amount,
                "Amount Paid": report.total_amount_paid,
                "Order Status": report.status.value,
            }
            flattened_data.append(flat_item)

    df = pd.DataFrame(flattened_data)

    if format == ExportFormat.excel:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sales Report')
        
        output.seek(0)
        
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=detailed_sales_report.xlsx"}
        )

    elif format == ExportFormat.pdf:  # NOTE: This route now generates a PDF for scalability.
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_pdf import PdfPages
            from pandas.plotting import table
            import textwrap
            import numpy as np

            output = io.BytesIO()
            # Use PdfPages to create a multi-page PDF document
            with PdfPages(output) as pdf:
                df_for_pdf = df.copy()

                # Drop columns not needed for PDF export
                columns_to_drop = ['SO Number', 'Order Status']
                df_for_pdf.drop(columns=[col for col in columns_to_drop if col in df_for_pdf.columns], inplace=True)

                # Rename columns for shorter headers in PDF
                df_for_pdf.rename(columns={
                    "Price Per Unit": "Unit Price",
                    "Bill No": "Bill#",
                    "Customer Name": "Customer",
                    "Order Date": "Date",
                    "Item Name": "Item",
                    "Variant Name": "Variant",
                    "Line Total": "Item Total",
                    "Order Total Amount": "SO Total",
                    "Amount Paid": "Paid",
                }, inplace=True)

                # Wrap text for better layout
                for col in ['Customer', 'Item']:
                    if col in df_for_pdf.columns:
                        df_for_pdf[col] = df_for_pdf[col].apply(
                            lambda x: '\n'.join(textwrap.wrap(str(x), width=20)) if isinstance(x, str) else x
                        )
                
                rows_per_page = 35  # Number of rows per PDF page
                num_pages = int(np.ceil(len(df_for_pdf) / rows_per_page))

                for i in range(num_pages):
                    chunk = df_for_pdf.iloc[i * rows_per_page : (i + 1) * rows_per_page]
                    
                    # Standard A4 size in landscape for more width
                    fig, ax = plt.subplots(figsize=(11.7, 8.3)) # A4 landscape
                    ax.axis('off')
                    
                    # Add a title to each page
                    ax.set_title(f"Detailed Sales Report - Page {i + 1} of {num_pages}", fontsize=14, pad=20)

                    the_table = table(ax, chunk, loc='center', cellLoc='left', colLoc='center')
                    the_table.auto_set_font_size(False)
                    the_table.set_fontsize(9) # Slightly smaller font for more data
                    the_table.scale(1, 1.5)  # Adjust vertical scaling

                    pdf.savefig(fig, bbox_inches='tight')
                    plt.close(fig)

            output.seek(0)

            # Return as PDF
            return StreamingResponse(
                output,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=detailed_sales_report.pdf"}
            )

        except Exception as e:
            logger.error(f"Failed to generate PDF report: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to generate PDF report: {str(e)}")

    else:
        # This case should not be reached due to Enum validation
        raise HTTPException(status_code=400, detail="Invalid format specified.")


@router.get("/", response_model=List[SalesOrderSchema])
def read_sales_orders(
    skip: int = 0,
    limit: int = 100,
    customer_id: Optional[int] = None,
    status: Optional[SalesOrderStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Retrieve a list of sales orders with various filters."""
    query = db.query(SalesOrderModel).filter(SalesOrderModel.tenant_id == tenant_id)

    if customer_id:
        query = query.filter(SalesOrderModel.customer_id == customer_id)
    if status:
        query = query.filter(SalesOrderModel.status == status)
    if start_date:
        query = query.filter(SalesOrderModel.order_date >= start_date)
    if end_date:
        query = query.filter(SalesOrderModel.order_date <= end_date)

    sales_orders = query.order_by(SalesOrderModel.order_date.desc(), SalesOrderModel.id.desc()).options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).offset(skip).limit(limit).all()
    
    return sales_orders

@router.get("/{so_id}", response_model=SalesOrderSchema)
def read_sales_order(so_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """Retrieve a single sales order by ID."""
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found")
    return db_so

@router.patch("/{so_id}", response_model=SalesOrderSchema)
def update_sales_order(
    so_id: int,
    so_update: SalesOrderUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Update an existing sales order."""
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items).selectinload(SalesOrderItemModel.inventory_item)
    ).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    old_values = sqlalchemy_to_dict(db_so)
    old_order_date = db_so.order_date
    so_data = so_update.model_dump(exclude_unset=True)
    
    new_order_date = so_data.get("order_date")

    if new_order_date and isinstance(new_order_date, str):
        new_order_date = datetime.fromisoformat(new_order_date).date()

    date_changed = new_order_date and new_order_date != old_order_date

    if date_changed:
        # Check for stock on the new date before making any changes
        for item in db_so.items:
            if item.inventory_item.name in EGG_ITEM_NAMES:
                available_stock = _get_available_egg_stock(db, tenant_id, new_order_date, item.inventory_item.name)
                if available_stock < item.quantity:
                    raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{item.inventory_item.name}' on new date {new_order_date}. Available: {available_stock}, Requested: {item.quantity}")

        egg_items_by_type = {"Table Egg": Decimal(0), "Jumbo Egg": Decimal(0), "Grade C Egg": Decimal(0)}
        has_egg_items = False
        for item in db_so.items:
            if item.inventory_item.name in EGG_ITEM_NAMES:
                has_egg_items = True
                egg_items_by_type[item.inventory_item.name] += item.quantity
        
        if has_egg_items:
            # Revert from old date report
            old_egg_room_report = db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == old_order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).first()
            if old_egg_room_report:
                # Atomically subtract from old date report to avoid race conditions
                db.query(EggRoomReportModel).filter(
                    EggRoomReportModel.report_date == old_order_date,
                    EggRoomReportModel.tenant_id == tenant_id
                ).update({
                    EggRoomReportModel.table_transfer: func.coalesce(EggRoomReportModel.table_transfer, 0) - int(egg_items_by_type["Table Egg"]),
                    EggRoomReportModel.jumbo_transfer: func.coalesce(EggRoomReportModel.jumbo_transfer, 0) - int(egg_items_by_type["Jumbo Egg"]),
                    EggRoomReportModel.grade_c_transfer: func.coalesce(EggRoomReportModel.grade_c_transfer, 0) - int(egg_items_by_type["Grade C Egg"])
                }, synchronize_session=False)

            # Apply to new date report
            new_egg_room_report = db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == new_order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).first()
            if not new_egg_room_report:
                logger.info(f"No egg room report found for {new_order_date}, creating one.")
                report_create = EggRoomReportCreate(
                    report_date=new_order_date,
                    table_damage=0,
                    table_out=0,
                    grade_c_labour=0,
                    grade_c_waste=0,
                    jumbo_waste=0,
                    jumbo_out=0)
                new_egg_room_report = crud_egg_room_reports.create_report(
                    db=db, 
                    report=report_create, 
                    tenant_id=tenant_id, 
                    user_id=get_user_identifier(user)
                )
            
            # Atomically add to new date report
            db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == new_order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).update({
                EggRoomReportModel.table_transfer: func.coalesce(EggRoomReportModel.table_transfer, 0) + int(egg_items_by_type["Table Egg"]),
                EggRoomReportModel.jumbo_transfer: func.coalesce(EggRoomReportModel.jumbo_transfer, 0) + int(egg_items_by_type["Jumbo Egg"]),
                EggRoomReportModel.grade_c_transfer: func.coalesce(EggRoomReportModel.grade_c_transfer, 0) + int(egg_items_by_type["Grade C Egg"])
            }, synchronize_session=False)

    # Note: SHIPPED and CANCELLED statuses are not set anywhere in backend.
    # Keep status changes minimal here; payments update payment-related statuses (PAID/PARTIALLY_PAID/APPROVED/DRAFT).
    # No inventory changes are handled here for SHIPPED because the backend does not transition to SHIPPED.

    so_data.pop("total_amount", None)

    for key, value in so_data.items():
        setattr(db_so, key, value)
    
    db_so.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_so.updated_by = get_user_identifier(user)
    
    new_values = sqlalchemy_to_dict(db_so)
    log_entry = AuditLogCreate(
        table_name='sales_orders',
        record_id=str(so_id),
        changed_by=get_user_identifier(user),
        action='UPDATE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)
    db.commit()
    db.refresh(db_so)
    
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    
    logger.info(f"Sales Order (ID: {so_id}) updated by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_so


@router.post("/{so_id}/items", response_model=SalesOrderSchema, status_code=status.HTTP_201_CREATED)
def add_item_to_sales_order(
    so_id: int,
    item_request: SalesOrderItemCreateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Add a new item to an existing sales order."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if not db_so:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    if db_so.status == SalesOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot add items to a sales order with status '{db_so.status.value}'.")

    db_inventory_item = db.query(InventoryItemModel).filter(
        InventoryItemModel.id == item_request.inventory_item_id, 
        InventoryItemModel.tenant_id == tenant_id
    ).first()
    if not db_inventory_item:
        raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_request.inventory_item_id} not found.")

    # Stock validation
    if db_inventory_item.name in EGG_ITEM_NAMES:
        available_stock = _get_available_egg_stock(db, tenant_id, db_so.order_date, db_inventory_item.name)
        if available_stock < item_request.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{db_inventory_item.name}'. Available: {available_stock}, Requested: {item_request.quantity}")
    else:
        if db_inventory_item.category != 'Supplies':
            raise HTTPException(status_code=400, detail=f"Item '{db_inventory_item.name}' cannot be sold. Only items in 'Supplies' category can be sold.")
        if db_inventory_item.current_stock < item_request.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{db_inventory_item.name}'. Available: {db_inventory_item.current_stock}, Requested: {item_request.quantity}")

    existing_item = db.query(SalesOrderItemModel).filter(
        SalesOrderItemModel.sales_order_id == so_id,
        SalesOrderItemModel.inventory_item_id == item_request.inventory_item_id,
        SalesOrderItemModel.tenant_id == tenant_id
    ).first()
    if existing_item:
        raise HTTPException(status_code=400, detail="This item already exists in this sales order. Use the update endpoint to change quantity.")

    line_total = item_request.quantity * item_request.price_per_unit
    db_so_item = SalesOrderItemModel(
        sales_order_id=so_id,
        inventory_item_id=item_request.inventory_item_id,
        quantity=item_request.quantity,
        price_per_unit=item_request.price_per_unit,
        line_total=line_total,
        tenant_id=tenant_id,
        variant_id=item_request.variant_id,
        variant_name=item_request.variant_name
    )
    db.add(db_so_item)
    
    db_so.total_amount += line_total
    
    # Stock deduction and EggRoomReport update
    inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_request.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
    if inv.name in EGG_ITEM_NAMES:
        egg_room_report = db.query(EggRoomReportModel).filter(
            EggRoomReportModel.report_date == db_so.order_date,
            EggRoomReportModel.tenant_id == tenant_id
        ).first()
        if not egg_room_report:
            logger.info(f"No egg room report found for {db_so.order_date} while adding item, creating one.")
            report_create = EggRoomReportCreate(
                report_date=db_so.order_date,
                table_damage=0, table_out=0, grade_c_labour=0, grade_c_waste=0,
                jumbo_waste=0, jumbo_out=0
            )
            egg_room_report = crud_egg_room_reports.create_report(
                db=db, report=report_create, tenant_id=tenant_id, user_id=get_user_identifier(user)
            )

        # Atomic update to avoid lost updates when concurrent requests modify the same report
        if inv.name == "Table Egg":
            db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == db_so.order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).update({EggRoomReportModel.table_transfer: func.coalesce(EggRoomReportModel.table_transfer, 0) + int(item_request.quantity)}, synchronize_session=False)
        elif inv.name == "Jumbo Egg":
            db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == db_so.order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).update({EggRoomReportModel.jumbo_transfer: func.coalesce(EggRoomReportModel.jumbo_transfer, 0) + int(item_request.quantity)}, synchronize_session=False)
        elif inv.name == "Grade C Egg":
            db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == db_so.order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).update({EggRoomReportModel.grade_c_transfer: func.coalesce(EggRoomReportModel.grade_c_transfer, 0) + int(item_request.quantity)}, synchronize_session=False)
    else:
        old_stock = inv.current_stock or 0
        inv.current_stock -= item_request.quantity
        db.add(inv)
        audit = InventoryItemAudit(
            inventory_item_id=inv.id, change_type="sale",
            change_amount=item_request.quantity, old_quantity=old_stock,
            new_quantity=inv.current_stock, changed_by=get_user_identifier(user),
            note=f"Added to SO #{so_id}", tenant_id=tenant_id
        )
        db.add(audit)

    db_so.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_so.updated_by = get_user_identifier(user)
    
    db.commit()
    db.refresh(db_so)

    # Re-query with relationships for a complete response object
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items).selectinload(SalesOrderItemModel.inventory_item),
        selectinload(SalesOrderModel.payments),
        selectinload(SalesOrderModel.customer)
    ).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()

    logger.info(f"Item {db_inventory_item.name} added to Sales Order (ID: {so_id}) by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_so


@router.patch("/{so_id}/items/{item_id}", response_model=SalesOrderSchema)
def update_sales_order_item(
    so_id: int,
    item_id: int,
    item_update: SalesOrderItemUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    logger.info(f"Updating sales order item {item_id} for SO {so_id} with data: {item_update.model_dump_json()}")
    """
    Update a specific item in a sales order.
    - If the inventory_item_id is changed, it's treated as a 'delete' of the old item
      and an 'add' of the new item to ensure correct stock and report handling.
    - If only quantity/price is changed, it adjusts the stock based on the delta.
    """
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items).selectinload(SalesOrderItemModel.inventory_item)
    ).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()

    if not db_so:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    item_to_update = next((item for item in db_so.items if item.id == item_id), None)
    if not item_to_update:
        raise HTTPException(status_code=404, detail="Sales Order Item not found")

    if db_so.status == SalesOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot modify items for a sales order with status '{db_so.status.value}'.")

    update_data = item_update.model_dump(exclude_unset=True)
    new_inventory_item_id = update_data.get("inventory_item_id")
    is_item_change = new_inventory_item_id and new_inventory_item_id != item_to_update.inventory_item_id

    if is_item_change:
        # --- Handle full item change (delete old, add new) ---
        
        # 1. Restore stock for the OLD item
        old_inv_item = item_to_update.inventory_item
        logger.info(f"[ITEM CHANGE] Old item: '{old_inv_item.name if old_inv_item else 'N/A'}' (ID: {item_to_update.inventory_item_id}), Quantity: {item_to_update.quantity}")
        if old_inv_item:
            if old_inv_item.name in EGG_ITEM_NAMES:
                egg_room_report = db.query(EggRoomReportModel).filter(
                    EggRoomReportModel.report_date == db_so.order_date,
                    EggRoomReportModel.tenant_id == tenant_id
                ).first()
                logger.info(f"[ITEM CHANGE] Old item is an egg. Found egg room report for {db_so.order_date}: {'Yes' if egg_room_report else 'No'}")
                if egg_room_report:
                    # Atomic subtraction
                    if old_inv_item.name == "Table Egg":
                        db.query(EggRoomReportModel).filter(
                            EggRoomReportModel.report_date == db_so.order_date,
                            EggRoomReportModel.tenant_id == tenant_id
                        ).update({EggRoomReportModel.table_transfer: func.coalesce(EggRoomReportModel.table_transfer, 0) - int(item_to_update.quantity)}, synchronize_session=False)
                    elif old_inv_item.name == "Jumbo Egg":
                        db.query(EggRoomReportModel).filter(
                            EggRoomReportModel.report_date == db_so.order_date,
                            EggRoomReportModel.tenant_id == tenant_id
                        ).update({EggRoomReportModel.jumbo_transfer: func.coalesce(EggRoomReportModel.jumbo_transfer, 0) - int(item_to_update.quantity)}, synchronize_session=False)
                    elif old_inv_item.name == "Grade C Egg":
                        db.query(EggRoomReportModel).filter(
                            EggRoomReportModel.report_date == db_so.order_date,
                            EggRoomReportModel.tenant_id == tenant_id
                        ).update({EggRoomReportModel.grade_c_transfer: func.coalesce(EggRoomReportModel.grade_c_transfer, 0) - int(item_to_update.quantity)}, synchronize_session=False)
            else:
                old_stock = old_inv_item.current_stock or 0
                logger.info(f"[ITEM CHANGE] Old item is not an egg. Restoring stock for '{old_inv_item.name}'. Old stock: {old_stock}, Quantity to restore: {item_to_update.quantity}")
                old_inv_item.current_stock += item_to_update.quantity
                db.add(old_inv_item)
                audit = InventoryItemAudit(
                    inventory_item_id=old_inv_item.id, change_type="return",
                    change_amount=item_to_update.quantity, old_quantity=old_stock,
                    new_quantity=old_inv_item.current_stock, changed_by=get_user_identifier(user),
                    note=f"Item changed on SO #{so_id}", tenant_id=tenant_id
                )
                db.add(audit)

        # 2. Validate and deduct stock for the NEW item
        new_inv_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == new_inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
        logger.info(f"[ITEM CHANGE] New item: '{new_inv_item.name if new_inv_item else 'N/A'}' (ID: {new_inventory_item_id})")
        if not new_inv_item:
            raise HTTPException(status_code=400, detail=f"New Inventory Item with ID {new_inventory_item_id} not found.")

        new_quantity = Decimal(update_data.get('quantity', item_to_update.quantity))
        logger.info(f"[ITEM CHANGE] New quantity: {new_quantity}")

        if new_inv_item.name in EGG_ITEM_NAMES:
            logger.info(f"[ITEM CHANGE] New item '{new_inv_item.name}' is an egg. Checking stock for date {db_so.order_date}.")
            available_stock = _get_available_egg_stock(db, tenant_id, db_so.order_date, new_inv_item.name)
            if available_stock < new_quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for new item '{new_inv_item.name}'. Available: {available_stock}, Requested: {new_quantity}")
            
            egg_room_report = db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == db_so.order_date, 
                EggRoomReportModel.tenant_id == tenant_id
            ).first()
            logger.info(f"[ITEM CHANGE] Found egg room report for {db_so.order_date} to deduct stock: {'Yes' if egg_room_report else 'No'}")
            if not egg_room_report:
                logger.info(f"No egg room report found for {db_so.order_date} while updating item, creating one.")
                report_create = EggRoomReportCreate(
                    report_date=db_so.order_date,
                    table_damage=0,
                    table_out=0,
                    grade_c_labour=0,
                    grade_c_waste=0,
                    jumbo_waste=0,
                    jumbo_out=0
                )
                egg_room_report = crud_egg_room_reports.create_report(
                    db=db, report=report_create, tenant_id=tenant_id, user_id=get_user_identifier(user)
                )
            if egg_room_report:
                logger.info(f"[ITEM CHANGE] Deducting {new_quantity} of '{new_inv_item.name}' from egg room report.")
                # Atomic addition
                if new_inv_item.name == "Table Egg":
                    db.query(EggRoomReportModel).filter(
                        EggRoomReportModel.report_date == db_so.order_date,
                        EggRoomReportModel.tenant_id == tenant_id
                    ).update({EggRoomReportModel.table_transfer: func.coalesce(EggRoomReportModel.table_transfer, 0) + int(new_quantity)}, synchronize_session=False)
                elif new_inv_item.name == "Jumbo Egg":
                    db.query(EggRoomReportModel).filter(
                        EggRoomReportModel.report_date == db_so.order_date,
                        EggRoomReportModel.tenant_id == tenant_id
                    ).update({EggRoomReportModel.jumbo_transfer: func.coalesce(EggRoomReportModel.jumbo_transfer, 0) + int(new_quantity)}, synchronize_session=False)
                elif new_inv_item.name == "Grade C Egg":
                    db.query(EggRoomReportModel).filter(
                        EggRoomReportModel.report_date == db_so.order_date,
                        EggRoomReportModel.tenant_id == tenant_id
                    ).update({EggRoomReportModel.grade_c_transfer: func.coalesce(EggRoomReportModel.grade_c_transfer, 0) + int(new_quantity)}, synchronize_session=False)
        else:
            if new_inv_item.category != 'Supplies':
                raise HTTPException(status_code=400, detail=f"Item '{new_inv_item.name}' cannot be sold. Only items in 'Supplies' category can be sold.")
            logger.info(f"[ITEM CHANGE] New item '{new_inv_item.name}' is not an egg. Checking inventory stock.")
            if (new_inv_item.current_stock or 0) < new_quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for new item '{new_inv_item.name}'. Available: {new_inv_item.current_stock}, Requested: {new_quantity}")
            
            old_stock = new_inv_item.current_stock or 0
            new_inv_item.current_stock -= new_quantity
            db.add(new_inv_item)
            audit = InventoryItemAudit(
                inventory_item_id=new_inv_item.id, change_type="sale",
                change_amount=new_quantity, old_quantity=old_stock,
                new_quantity=new_inv_item.current_stock, changed_by=get_user_identifier(user),
                note=f"Item changed on SO #{so_id}", tenant_id=tenant_id
            )
            db.add(audit)
        
        # 3. Update the item in the database
        for key, value in update_data.items():
            setattr(item_to_update, key, value)

    else:
        # --- Handle only quantity/price change ---
        old_qty = item_to_update.quantity
        new_qty = Decimal(update_data.get('quantity', old_qty))
        delta = new_qty - old_qty

        if delta != 0:
            inv = item_to_update.inventory_item
            if inv.name in EGG_ITEM_NAMES:
                if delta > 0:
                    available_stock = _get_available_egg_stock(db, tenant_id, db_so.order_date, inv.name)
                    if available_stock < delta:
                        raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{inv.name}'. Available: {available_stock}, Required additional: {delta}")
                
                egg_room_report = db.query(EggRoomReportModel).filter(EggRoomReportModel.report_date == db_so.order_date, EggRoomReportModel.tenant_id == tenant_id).first()
                if not egg_room_report:
                    logger.info(f"No egg room report found for {db_so.order_date} while updating item quantity, creating one.")
                    report_create = EggRoomReportCreate(
                        report_date=db_so.order_date,
                        table_damage=0, table_out=0, grade_c_labour=0, grade_c_waste=0,
                        jumbo_waste=0, jumbo_out=0
                    )
                    egg_room_report = crud_egg_room_reports.create_report(
                        db=db, report=report_create, tenant_id=tenant_id, user_id=get_user_identifier(user)
                    )
                
                # Atomic adjustment for quantity delta
                if inv.name == "Table Egg":
                    db.query(EggRoomReportModel).filter(
                        EggRoomReportModel.report_date == db_so.order_date,
                        EggRoomReportModel.tenant_id == tenant_id
                    ).update({EggRoomReportModel.table_transfer: func.coalesce(EggRoomReportModel.table_transfer, 0) + int(delta)}, synchronize_session=False)
                elif inv.name == "Jumbo Egg":
                    db.query(EggRoomReportModel).filter(
                        EggRoomReportModel.report_date == db_so.order_date,
                        EggRoomReportModel.tenant_id == tenant_id
                    ).update({EggRoomReportModel.jumbo_transfer: func.coalesce(EggRoomReportModel.jumbo_transfer, 0) + int(delta)}, synchronize_session=False)
                elif inv.name == "Grade C Egg":
                    db.query(EggRoomReportModel).filter(
                        EggRoomReportModel.report_date == db_so.order_date,
                        EggRoomReportModel.tenant_id == tenant_id
                    ).update({EggRoomReportModel.grade_c_transfer: func.coalesce(EggRoomReportModel.grade_c_transfer, 0) + int(delta)}, synchronize_session=False)
            else:
                inv_with_lock = db.query(InventoryItemModel).filter(InventoryItemModel.id == inv.id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
                if delta > 0 and inv_with_lock.current_stock < delta:
                    raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{inv.name}'. Available: {inv_with_lock.current_stock}, Required additional: {delta}")
                
                old_stock = inv_with_lock.current_stock or 0
                inv_with_lock.current_stock -= delta
                db.add(inv_with_lock)
                audit = InventoryItemAudit(
                    inventory_item_id=inv.id, change_type="sale_adjustment",
                    change_amount=-delta, old_quantity=old_stock,
                    new_quantity=inv_with_lock.current_stock, changed_by=get_user_identifier(user),
                    note=f"Quantity updated on SO #{so_id}", tenant_id=tenant_id
                )
                db.add(audit)

        for key, value in update_data.items():
            setattr(item_to_update, key, value)

    # Recalculate totals and commit
    item_to_update.line_total = item_to_update.quantity * item_to_update.price_per_unit
    
    db_so.total_amount = sum(item.line_total for item in db_so.items)
    db_so.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_so.updated_by = get_user_identifier(user)

    db.commit()
    db.refresh(db_so)

    logger.info(f"Sales Order Item (ID: {item_id}) of Sales Order (ID: {so_id}) updated by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_so

@router.delete("/{so_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sales_order_item(
    so_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Delete a specific item from a sales order."""
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items).selectinload(SalesOrderItemModel.inventory_item)
    ).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if not db_so:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    item_to_delete = None
    for item in db_so.items:
        if item.id == item_id:
            item_to_delete = item
            break

    if not item_to_delete:
        raise HTTPException(status_code=404, detail="Sales Order Item not found")

    # Do not allow item deletion for finalized sales orders
    if db_so.status == SalesOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot delete items from a sales order with status '{db_so.status.value}'.")

    # Restore inventory for the deleted item
    inv = db.query(InventoryItemModel).filter(
        InventoryItemModel.id == item_to_delete.inventory_item_id,
        InventoryItemModel.tenant_id == tenant_id
    ).with_for_update().first()

    if inv:
        # --- Stock restoration logic --- 
        if inv.name in EGG_ITEM_NAMES:
            # For eggs, stock is managed via EggRoomReport, so no direct update to InventoryItem.current_stock
            # Update egg room report by subtracting the quantity from transfer
            egg_room_report = db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == db_so.order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).first()

            if egg_room_report:
                # Atomic subtraction when deleting an item
                if inv.name == "Table Egg":
                    db.query(EggRoomReportModel).filter(
                        EggRoomReportModel.report_date == db_so.order_date,
                        EggRoomReportModel.tenant_id == tenant_id
                    ).update({EggRoomReportModel.table_transfer: func.coalesce(EggRoomReportModel.table_transfer, 0) - int(item_to_delete.quantity)}, synchronize_session=False)
                elif inv.name == "Jumbo Egg":
                    db.query(EggRoomReportModel).filter(
                        EggRoomReportModel.report_date == db_so.order_date,
                        EggRoomReportModel.tenant_id == tenant_id
                    ).update({EggRoomReportModel.jumbo_transfer: func.coalesce(EggRoomReportModel.jumbo_transfer, 0) - int(item_to_delete.quantity)}, synchronize_session=False)
                elif inv.name == "Grade C Egg":
                    db.query(EggRoomReportModel).filter(
                        EggRoomReportModel.report_date == db_so.order_date,
                        EggRoomReportModel.tenant_id == tenant_id
                    ).update({EggRoomReportModel.grade_c_transfer: func.coalesce(EggRoomReportModel.grade_c_transfer, 0) - int(item_to_delete.quantity)}, synchronize_session=False)
        else:
            # For non-egg items, restore current_stock
            old_stock = inv.current_stock or 0
            inv.current_stock = (inv.current_stock or 0) + item_to_delete.quantity
            db.add(inv)

            # Create audit record for inventory increase (item deleted from SO)
            audit = InventoryItemAudit(
                inventory_item_id=inv.id,
                change_type="return", # Or "sales_order_item_deleted"
                change_amount=item_to_delete.quantity,
                old_quantity=old_stock,
                new_quantity=inv.current_stock,
                changed_by=get_user_identifier(user),
                note=f"Item deleted from SO #{so_id} (Item ID: {item_id})",
                tenant_id=tenant_id
            )
            db.add(audit)
        # --- End stock restoration logic ---

    # Update the total_amount on the parent Sales Order
    db_so.total_amount -= item_to_delete.line_total
    db_so.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_so.updated_by = get_user_identifier(user)

    db.delete(item_to_delete)
    db.commit()
    db.refresh(db_so)

    logger.info(
        f"Sales Order Item (ID: {item_id}) deleted from Sales Order (ID: {so_id}) by user {get_user_identifier(user)} for tenant {tenant_id}"
    )
    return {"message": "Sales Order Item deleted successfully"}

@router.delete("/{so_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sales_order(
    so_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Delete a sales order."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    if db_so.status != SalesOrderStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sales Order status is '{db_so.status.value}'. Only 'Draft' SOs can be deleted."
        )

    # ADDED: Update egg room report for egg sales
    table_egg_qty = 0
    jumbo_egg_qty = 0
    grade_c_egg_qty = 0

    for item in db_so.items:
        db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
        if db_inventory_item:
            if db_inventory_item.name == "Table Egg":
                table_egg_qty += item.quantity
            elif db_inventory_item.name == "Jumbo Egg":
                jumbo_egg_qty += item.quantity
            elif db_inventory_item.name == "Grade C Egg":
                grade_c_egg_qty += item.quantity

    if table_egg_qty > 0 or jumbo_egg_qty > 0 or grade_c_egg_qty > 0:
        egg_room_report = db.query(EggRoomReportModel).filter(
            EggRoomReportModel.report_date == db_so.order_date,
            EggRoomReportModel.tenant_id == tenant_id
        ).first()

        if egg_room_report:
            # Use atomic updates with COALESCE to handle NULL values
            db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == db_so.order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).update({
                EggRoomReportModel.table_transfer: func.coalesce(EggRoomReportModel.table_transfer, 0) - int(table_egg_qty),
                EggRoomReportModel.jumbo_transfer: func.coalesce(EggRoomReportModel.jumbo_transfer, 0) - int(jumbo_egg_qty),
                EggRoomReportModel.grade_c_transfer: func.coalesce(EggRoomReportModel.grade_c_transfer, 0) - int(grade_c_egg_qty)
            }, synchronize_session=False)

    # Restore inventory for items on the deleted sales order
    for item in db_so.items:
        inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
        if inv:
            inv.current_stock = (inv.current_stock or 0) + item.quantity
            db.add(inv)
    old_values = sqlalchemy_to_dict(db_so)
    db_so.deleted_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_so.deleted_by = get_user_identifier(user)
    new_values = sqlalchemy_to_dict(db_so)
    log_entry = AuditLogCreate(
        table_name='sales_orders',
        record_id=str(so_id),
        changed_by=get_user_identifier(user),
        action='DELETE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)
    db.commit()
    logger.info(f"Sales Order (ID: {so_id}) soft deleted by user {get_user_identifier(user)} for tenant {tenant_id}")
    return {"message": "Sales Order deleted successfully"}


@router.get("/{so_id}/receipt", response_class=FileResponse)
def get_sales_order_receipt(so_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    """
    Generate and return a PDF receipt for a single sales order.
    """
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if db_so is None:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    try:
        filepath = generate_sales_order_receipt(db, so_id)
        filename = os.path.basename(filepath)
        return FileResponse(filepath, media_type='application/pdf', filename=filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to generate receipt for SO {so_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate receipt: {str(e)}")


class ReceiptUploadRequest(BaseModel):
    filename: str

@router.post("/{so_id}/receipt-upload-url")
def get_receipt_upload_url(
    so_id: int,
    request_body: ReceiptUploadRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a pre-signed URL for uploading a sales order receipt."""
    if not generate_presigned_upload_url:
        raise HTTPException(status_code=501, detail="S3 upload functionality is not configured.")

    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if not db_so:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    try:
        upload_data = generate_presigned_upload_url(
            tenant_id=tenant_id,
            object_id=so_id,
            filename=request_body.filename
        )
        
        db_so.payment_receipt = upload_data["s3_path"]
        db.commit()

        return {"upload_url": upload_data["upload_url"], "s3_path": upload_data["s3_path"]}

    except Exception as e:
        logger.exception(f"Failed to generate presigned URL for SO {so_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")

@router.get("/{so_id}/receipt-download-url")
def get_receipt_download_url(
    so_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a pre-signed URL for downloading a sales order receipt."""
    if not generate_presigned_download_url:
        raise HTTPException(status_code=501, detail="S3 download functionality is not configured.")

    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if not db_so or not db_so.payment_receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")

    if not db_so.payment_receipt.startswith('s3://'):
        raise HTTPException(status_code=400, detail="Receipt is not stored in S3.")

    try:
        download_url = generate_presigned_download_url(s3_path=db_so.payment_receipt)
        return {"download_url": download_url}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to generate download URL for SO {so_id}")
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")
