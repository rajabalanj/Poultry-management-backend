from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from utils.auth_utils import get_current_user, get_user_identifier
from datetime import datetime
from crud.audit_log import create_audit_log
from schemas.audit_log import AuditLogCreate
from utils import sqlalchemy_to_dict

from database import get_db
from models.business_partners import BusinessPartner as BusinessPartnerModel
from models.purchase_orders import PurchaseOrder as PurchaseOrderModel
from models.sales_orders import SalesOrder as SalesOrderModel
from schemas.business_partners import BusinessPartner, BusinessPartnerCreate, BusinessPartnerUpdate, PartnerStatus
import pytz
from utils.tenancy import get_tenant_id

router = APIRouter(prefix="/business-partners", tags=["Business Partners"])
logger = logging.getLogger("business_partners")

@router.post("/", response_model=BusinessPartner, status_code=status.HTTP_201_CREATED)
def create_business_partner(
    partner: BusinessPartnerCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    db_partner = db.query(BusinessPartnerModel).filter(BusinessPartnerModel.name == partner.name, BusinessPartnerModel.tenant_id == tenant_id).first()
    if db_partner:
        raise HTTPException(status_code=400, detail="Business partner with this name already exists")
    
    db_partner = BusinessPartnerModel(**partner.model_dump(), tenant_id=tenant_id, created_by=get_user_identifier(user))
    db.add(db_partner)
    db.commit()
    db.refresh(db_partner)
    logger.info(f"Business partner '{db_partner.name}' created by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_partner

@router.get("/", response_model=List[BusinessPartner])
def read_business_partners(
    skip: int = 0,
    limit: int = 100,
    status: Optional[PartnerStatus] = None,
    is_vendor: Optional[bool] = Query(None),
    is_customer: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id)
):
    query = db.query(BusinessPartnerModel).filter(BusinessPartnerModel.tenant_id == tenant_id)
    if status:
        query = query.filter(BusinessPartnerModel.status == status)
    if is_vendor is not None:
        query = query.filter(BusinessPartnerModel.is_vendor == is_vendor)
    if is_customer is not None:
        query = query.filter(BusinessPartnerModel.is_customer == is_customer)
    return query.offset(skip).limit(limit).all()

@router.get("/{partner_id}", response_model=BusinessPartner)
def read_business_partner(partner_id: int, db: Session = Depends(get_db), tenant_id: str = Depends(get_tenant_id)):
    db_partner = db.query(BusinessPartnerModel).filter(BusinessPartnerModel.id == partner_id, BusinessPartnerModel.tenant_id == tenant_id).first()
    if db_partner is None:
        raise HTTPException(status_code=404, detail="Business partner not found")
    return db_partner

@router.patch("/{partner_id}", response_model=BusinessPartner)
def update_business_partner(
    partner_id: int,
    partner: BusinessPartnerUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    db_partner = db.query(BusinessPartnerModel).filter(BusinessPartnerModel.id == partner_id, BusinessPartnerModel.tenant_id == tenant_id).first()
    if db_partner is None:
        raise HTTPException(status_code=404, detail="Business partner not found")
    
    old_values = sqlalchemy_to_dict(db_partner)

    if partner.name is not None and partner.name != db_partner.name:
        existing_partner = db.query(BusinessPartnerModel).filter(BusinessPartnerModel.name == partner.name, BusinessPartnerModel.tenant_id == tenant_id).first()
        if existing_partner:
            raise HTTPException(status_code=400, detail="Business partner with this name already exists")

    partner_data = partner.model_dump(exclude_unset=True)
    for key, value in partner_data.items():
        setattr(db_partner, key, value)
    db_partner.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_partner.updated_by = get_user_identifier(user)
    
    new_values = sqlalchemy_to_dict(db_partner)
    log_entry = AuditLogCreate(
        table_name='business_partners',
        record_id=str(partner_id),
        changed_by=get_user_identifier(user),
        action='UPDATE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)
    db.commit()
    db.refresh(db_partner)
    logger.info(f"Business partner '{db_partner.name}' (ID: {partner_id}) updated by user {get_user_identifier(user)} for tenant {tenant_id}")
    return db_partner

@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business_partner(
    partner_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id)
):
    db_partner = db.query(BusinessPartnerModel).filter(BusinessPartnerModel.id == partner_id, BusinessPartnerModel.tenant_id == tenant_id).first()
    if db_partner is None:
        raise HTTPException(status_code=404, detail="Business partner not found")

    # Check for associated orders
    has_purchases = db.query(PurchaseOrderModel).filter(PurchaseOrderModel.vendor_id == partner_id).first()
    has_sales = db.query(SalesOrderModel).filter(SalesOrderModel.customer_id == partner_id).first()
    
    if has_purchases or has_sales:
        db_partner.status = PartnerStatus.INACTIVE
        db.commit()
        logger.warning(f"Business partner '{db_partner.name}' (ID: {partner_id}) set to INACTIVE due to associated orders by user {get_user_identifier(user)} for tenant {tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Business partner '{db_partner.name}' has associated orders. Status changed to Inactive."
        )
    
    old_values = sqlalchemy_to_dict(db_partner)

    # Instead of deleting, mark the partner as INACTIVE
    db_partner.status = PartnerStatus.INACTIVE
    db_partner.updated_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    db_partner.updated_by = get_user_identifier(user)
    new_values = sqlalchemy_to_dict(db_partner)

    log_entry = AuditLogCreate(
        table_name='business_partners',
        record_id=str(partner_id),
        changed_by=get_user_identifier(user),
        action='DEACTIVATE',
        old_values=old_values,
        new_values=new_values
    )
    create_audit_log(db=db, log_entry=log_entry)

    db.commit()
    logger.info(f"Business partner '{db_partner.name}' (ID: {partner_id}) set to INACTIVE by user {get_user_identifier(user)} for tenant {tenant_id}")
    return {"message": "Business partner set to Inactive"}
