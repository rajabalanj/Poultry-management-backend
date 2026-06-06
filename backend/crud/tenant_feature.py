from sqlalchemy.orm import Session
from models.tenant_feature import TenantFeature
from schemas.tenant_feature import TenantFeatureCreate, TenantFeatureUpdate

def get_tenant_features(db: Session, skip: int = 0, limit: int = 100):
    return db.query(TenantFeature).offset(skip).limit(limit).all()

def get_features_by_tenant(db: Session, tenant_id: str):
    return db.query(TenantFeature).filter(TenantFeature.tenant_id == tenant_id).all()

def create_tenant_feature(db: Session, feature: TenantFeatureCreate):
    db_feature = TenantFeature(
        tenant_id=feature.tenant_id,
        feature_name=feature.feature_name,
        is_restricted=feature.is_restricted
    )
    db.add(db_feature)
    db.commit()
    db.refresh(db_feature)
    return db_feature

def update_tenant_feature(db: Session, feature_id: int, feature_update: TenantFeatureUpdate):
    db_feature = db.query(TenantFeature).filter(TenantFeature.id == feature_id).first()
    if db_feature:
        update_data = feature_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_feature, key, value)
        db.commit()
        db.refresh(db_feature)
    return db_feature

def delete_tenant_feature(db: Session, feature_id: int):
    db_feature = db.query(TenantFeature).filter(TenantFeature.id == feature_id).first()
    if db_feature:
        db.delete(db_feature)
        db.commit()
        return True
    return False