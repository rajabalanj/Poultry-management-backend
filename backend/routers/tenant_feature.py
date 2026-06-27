from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas.tenant_feature import TenantFeature, TenantFeatureCreate, TenantFeatureUpdate
from crud import tenant_feature as crud_tenant_feature
from utils.auth_utils import require_group, get_current_user
from utils.tenancy import get_tenant_id

router = APIRouter(
    prefix="/tenant-features",
    tags=["Super Admin - Tenant Features"]
)

@router.get("", response_model=List[TenantFeature], dependencies=[Depends(require_group(["super_admin"]))])
def read_all_tenant_features(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud_tenant_feature.get_tenant_features(db=db, skip=skip, limit=limit)

@router.get("/{tenant_id}", response_model=List[TenantFeature])
def read_features_for_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    req_tenant_id: str = Depends(get_tenant_id)
):
    # Only allow super_admin, or if the user is fetching their own tenant's features
    is_super_admin = "super_admin" in user.get("cognito:groups", [])
    if not is_super_admin and tenant_id != req_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view feature restrictions for this tenant."
        )
    return crud_tenant_feature.get_features_by_tenant(db=db, tenant_id=tenant_id)

@router.post("", response_model=TenantFeature, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_group(["super_admin"]))])
def create_tenant_feature(feature: TenantFeatureCreate, db: Session = Depends(get_db)):
    # Check if this rule already exists to prevent duplicates
    existing_features = crud_tenant_feature.get_features_by_tenant(db=db, tenant_id=feature.tenant_id)
    if any(f.feature_name == feature.feature_name for f in existing_features):
        raise HTTPException(status_code=400, detail="Feature restriction already exists for this tenant.")
    return crud_tenant_feature.create_tenant_feature(db=db, feature=feature)

@router.patch("/{feature_id}", response_model=TenantFeature, dependencies=[Depends(require_group(["super_admin"]))])
def update_tenant_feature(feature_id: int, feature: TenantFeatureUpdate, db: Session = Depends(get_db)):
    db_feature = crud_tenant_feature.update_tenant_feature(db=db, feature_id=feature_id, feature_update=feature)
    if not db_feature:
        raise HTTPException(status_code=404, detail="Tenant Feature record not found")
    return db_feature

@router.delete("/{feature_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_group(["super_admin"]))])
def delete_tenant_feature(feature_id: int, db: Session = Depends(get_db)):
    if not crud_tenant_feature.delete_tenant_feature(db=db, feature_id=feature_id):
        raise HTTPException(status_code=404, detail="Tenant Feature record not found")