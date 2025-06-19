from sqlalchemy.orm import Session
from models.app_config import AppConfig
from schemas.app_config import AppConfigCreate, AppConfigUpdate

def create_config(db: Session, config: AppConfigCreate):
    db_config = AppConfig(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

def get_config(db: Session):
    return db.query(AppConfig).order_by(AppConfig.id.desc()).first()

def update_config(db: Session, config_id: int, config: AppConfigUpdate):
    db_config = db.query(AppConfig).filter(AppConfig.id == config_id).first()
    if not db_config:
        return None
    for field, value in config.dict(exclude_unset=True).items():
        setattr(db_config, field, value)
    db.commit()
    db.refresh(db_config)
    return db_config