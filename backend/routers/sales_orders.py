from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
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
import pytz
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict

try:
    from utils.s3_upload import upload_receipt_to_s3
except ImportError:
    upload_receipt_to_s3 = None

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
            if db_inventory_item.current_stock is not None and db_inventory_item.current_stock < item_data.quantity:
                raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{db_inventory_item.name}'. Available: {db_inventory_item.current_stock}, Requested: {item_data.quantity}")
        # --- End stock validation logic --- 
        
        # Price is now optional at creation. Default to 0 if not provided.
        price_per_unit = item_data.price_per_unit if item_data.price_per_unit is not None else Decimal("0.0")
        
        line_total = item_data.quantity * price_per_unit
        total_amount += line_total
        
        db_so_items.append(
            SalesOrderItemModel(
                inventory_item_id=item_data.inventory_item_id,
                quantity=item_data.quantity,
                price_per_unit=price_per_unit,
                line_total=line_total,
                tenant_id=tenant_id
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
        tenant_id=tenant_id
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

        if egg_room_report:
            egg_room_report.table_transfer += table_egg_qty
            egg_room_report.jumbo_transfer += jumbo_egg_qty
            egg_room_report.grade_c_transfer += grade_c_egg_qty
            db.add(egg_room_report)
            db.commit()

    db.refresh(db_so)
    
    db_so = db.query(SalesOrderModel).options(
        selectinload(SalesOrderModel.items),
        selectinload(SalesOrderModel.payments)
    ).filter(SalesOrderModel.id == db_so.id, SalesOrderModel.tenant_id == tenant_id).first()

    logger.info(f"Sales Order (ID: {db_so.id}) created for Customer ID {db_so.customer_id} by User {get_user_identifier(user)} for tenant {tenant_id}")
    return db_so

EGG_ITEM_NAMES = ["Table Egg", "Jumbo Egg", "Grade C Egg"]

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
                old_egg_room_report.table_transfer -= egg_items_by_type["Table Egg"]
                old_egg_room_report.jumbo_transfer -= egg_items_by_type["Jumbo Egg"]
                old_egg_room_report.grade_c_transfer -= egg_items_by_type["Grade C Egg"]
                db.add(old_egg_room_report)

            # Apply to new date report
            new_egg_room_report = db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == new_order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).first()
            if not new_egg_room_report:
                logger.info(f"No egg room report found for {new_order_date}, creating one.")
                report_create = EggRoomReportCreate(report_date=new_order_date)
                new_egg_room_report = crud_egg_room_reports.create_report(
                    db=db, 
                    report=report_create, 
                    tenant_id=tenant_id, 
                    user_id=get_user_identifier(user)
                )
            
            new_egg_room_report.table_transfer += egg_items_by_type["Table Egg"]
            new_egg_room_report.jumbo_transfer += egg_items_by_type["Jumbo Egg"]
            new_egg_room_report.grade_c_transfer += egg_items_by_type["Grade C Egg"]
            db.add(new_egg_room_report)

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

    # Restrict adding items based on SO status (only prevent adding when fully paid)
    if db_so.status == SalesOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot add items to a sales order with status '{db_so.status.value}'.")

    # Validate that the inventory item exists
    db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_request.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
    if not db_inventory_item:
        raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_request.inventory_item_id} not found.")

    # --- Stock validation logic --- 
    if db_inventory_item.name in EGG_ITEM_NAMES:
        available_stock = _get_available_egg_stock(db, tenant_id, db_so.order_date, db_inventory_item.name)
        if available_stock < item_request.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{db_inventory_item.name}'. Available: {available_stock}, Requested: {item_request.quantity}")
    else:
        if db_inventory_item.current_stock < item_request.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{db_inventory_item.name}'. Available: {db_inventory_item.current_stock}, Requested: {item_request.quantity}")
    # --- End stock validation logic --- 

    # Check if item already exists in this SO to prevent duplicates
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
        tenant_id=tenant_id
    )
    db.add(db_so_item)
    
    # Update the total_amount on the parent Sales Order
    db_so.total_amount += line_total
    db_so.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_so.updated_by = get_user_identifier(user)
    # Deduct inventory for this added item
    inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_request.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
    if inv is None:
        raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_request.inventory_item_id} not found when updating stock.")
    
    # --- Stock deduction logic --- 
    if inv.name in EGG_ITEM_NAMES:
        # For eggs, stock is managed via EggRoomReport, so no deduction from InventoryItem.current_stock
        pass # Stock deduction for eggs happens in the EggRoomReport update section below
    else:
        if inv.current_stock is None or inv.current_stock < item_request.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{getattr(inv, 'name', item_request.inventory_item_id)}'. Available: {inv.current_stock}, Required: {item_request.quantity}")

        old_stock = inv.current_stock or 0
        inv.current_stock -= item_request.quantity
        db.add(inv)

        # Create audit record for inventory decrease from adding SO item
        audit = InventoryItemAudit(
            inventory_item_id=inv.id,
            change_type="sale",
            change_amount=item_request.quantity,
            old_quantity=old_stock,
            new_quantity=inv.current_stock,
            changed_by=get_user_identifier(user),
            note=f"Added to SO #{so_id}",
            tenant_id=tenant_id
        )
        db.add(audit)
    # --- End stock deduction logic --- 
    
    db.commit()

    # ADDED: Update egg room report for egg sales
    db_inventory_item = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_request.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
    if db_inventory_item:
        egg_room_report = db.query(EggRoomReportModel).filter(
            EggRoomReportModel.report_date == db_so.order_date,
            EggRoomReportModel.tenant_id == tenant_id
        ).first()

        if egg_room_report:
            if db_inventory_item.name == "Table Egg":
                egg_room_report.table_transfer += item_request.quantity
            elif db_inventory_item.name == "Jumbo Egg":
                egg_room_report.jumbo_transfer += item_request.quantity
            elif db_inventory_item.name == "Grade C Egg":
                egg_room_report.grade_c_transfer += item_request.quantity
            db.add(egg_room_report)
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
    """Update a specific item in a sales order."""
    db_so = (
        db.query(SalesOrderModel)
        .options(selectinload(SalesOrderModel.items))
        .filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id)
        .first()
    )
    if not db_so:
        raise HTTPException(status_code=404, detail="Sales Order not found")

    item_to_update = None
    for item in db_so.items:
        if item.id == item_id:
            item_to_update = item
            break

    if not item_to_update:
        raise HTTPException(status_code=404, detail="Sales Order Item not found")

    # Do not allow item updates for finalized sales orders
    if db_so.status == SalesOrderStatus.PAID:
        raise HTTPException(status_code=400, detail=f"Cannot modify items for a sales order with status '{db_so.status.value}'.")

    # Capture old quantity then apply updates and adjust inventory by the delta
    old_qty = item_to_update.quantity
    update_data = item_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item_to_update, key, value)

    # Recalculate line total and order total amount
    item_to_update.line_total = item_to_update.quantity * item_to_update.price_per_unit
    # Adjust inventory by the difference
    new_qty = item_to_update.quantity
    delta = new_qty - old_qty

    # ADDED: Update egg room report for egg sales
    if delta != 0:
        inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_to_update.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).first()
        if inv:
            egg_room_report = db.query(EggRoomReportModel).filter(
                EggRoomReportModel.report_date == db_so.order_date,
                EggRoomReportModel.tenant_id == tenant_id
            ).first()

            if egg_room_report:
                if inv.name == "Table Egg":
                    egg_room_report.table_transfer += delta
                elif inv.name == "Jumbo Egg":
                    egg_room_report.jumbo_transfer += delta
                elif inv.name == "Grade C Egg":
                    egg_room_report.grade_c_transfer += delta
                db.add(egg_room_report)

    if delta != 0:
        inv = db.query(InventoryItemModel).filter(InventoryItemModel.id == item_to_update.inventory_item_id, InventoryItemModel.tenant_id == tenant_id).with_for_update().first()
        if inv is None:
            raise HTTPException(status_code=400, detail=f"Inventory Item with ID {item_to_update.inventory_item_id} not found when updating stock.")
        
        # --- Stock validation and deduction logic --- 
        if inv.name in EGG_ITEM_NAMES:
            if delta > 0: # If quantity increased, check egg stock
                available_stock = _get_available_egg_stock(db, tenant_id, db_so.order_date, inv.name)
                if available_stock < delta:
                    raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{inv.name}'. Available: {available_stock}, Required additional: {delta}")
            # No direct deduction from InventoryItem.current_stock for eggs
            pass
        else:
            if delta > 0:
                # Need more stock
                if inv.current_stock is None or inv.current_stock < delta:
                    raise HTTPException(status_code=400, detail=f"Insufficient stock for item '{getattr(inv, 'name', item_to_update.inventory_item_id)}'. Available: {inv.current_stock}, Required additional: {delta}")
                old_stock = inv.current_stock or 0
                inv.current_stock -= delta
                db.add(inv)

                # Create audit record for inventory decrease due to increasing SO item quantity
                audit = InventoryItemAudit(
                    inventory_item_id=inv.id,
                    change_type="sale",
                    change_amount=delta,
                    old_quantity=old_stock,
                    new_quantity=inv.current_stock,
                    changed_by=get_user_identifier(user),
                    note=f"Increased quantity on SO #{so_id} (Item ID: {item_id})",
                    tenant_id=tenant_id
                )
                db.add(audit)
            else:
                # Returned/reduced quantity -> restore stock
                restore_amount = -delta
                old_stock = inv.current_stock or 0
                inv.current_stock = (inv.current_stock or 0) + restore_amount
                db.add(inv)
                # (Optional) create a return/adjustment audit if desired
        # --- End stock validation and deduction logic --- 

    total_amount = sum(item.line_total for item in db_so.items)
    db_so.total_amount = total_amount
    db_so.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_so.updated_by = get_user_identifier(user)

    db.commit()
    db.refresh(db_so)

    logger.info(
        f"Sales Order Item (ID: {item_id}) of Sales Order (ID: {so_id}) updated by user {get_user_identifier(user)} for tenant {tenant_id}"
    )
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
                if inv.name == "Table Egg":
                    egg_room_report.table_transfer -= item_to_delete.quantity
                elif inv.name == "Jumbo Egg":
                    egg_room_report.jumbo_transfer -= item_to_delete.quantity
                elif inv.name == "Grade C Egg":
                    egg_room_report.grade_c_transfer -= item_to_delete.quantity
                db.add(egg_room_report)
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
            egg_room_report.table_transfer -= table_egg_qty
            egg_room_report.jumbo_transfer -= jumbo_egg_qty
            egg_room_report.grade_c_transfer -= grade_c_egg_qty
            db.add(egg_room_report)

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

@router.post("/{so_id}/receipt")
def upload_payment_receipt(
    so_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    """Upload payment receipt for a sales order."""
    db_so = db.query(SalesOrderModel).filter(SalesOrderModel.id == so_id, SalesOrderModel.tenant_id == tenant_id).first()
    if not db_so:
        raise HTTPException(status_code=404, detail="Sales Order not found")
    
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PDF and image files allowed")
    
    upload_dir = f"uploads/sales_receipts/{tenant_id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{so_id}_{uuid.uuid4().hex}.{file_extension}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    content = file.file.read()
    
    if os.getenv('AWS_ENVIRONMENT') and upload_receipt_to_s3:
        try:
            s3_url = upload_receipt_to_s3(content, file.filename, so_id)
            db_so.payment_receipt = s3_url
        except Exception as e:
            logger.exception(f"S3 upload failed for SO {so_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload to S3: {str(e)}")
    else:
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        db_so.payment_receipt = file_path
    
    db.commit()
    return {"message": "Receipt uploaded successfully", "file_path": db_so.payment_receipt}