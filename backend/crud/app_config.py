from sqlalchemy.orm import Session
from models.app_config import AppConfig
from schemas.app_config import AppConfigCreate, AppConfigUpdate

# Create a new config entry
def create_config(db: Session, config: AppConfigCreate):
    db_config = AppConfig(name=config.name, value=config.value)
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

# Get config by name (or all configs)
def get_config(db: Session, name: str = None):
    if name:
        return db.query(AppConfig).filter(AppConfig.name == name).first()
    return db.query(AppConfig).all()

# Update config by id or name
def update_config(db: Session, config_id: int, config: AppConfigUpdate):
    db_config = db.query(AppConfig).filter(AppConfig.id == config_id).first()
    if not db_config:
        return None
    for field, value in config.model_dump(exclude_unset=True).items():
        setattr(db_config, field, value)
    db.commit()
    db.refresh(db_config)
    return db_config

# Update config by name
def update_config_by_name(db: Session, name: str, config: AppConfigUpdate):
    db_config = db.query(AppConfig).filter(AppConfig.name == name).first()
    if not db_config:
        return None
    for field, value in config.model_dump(exclude_unset=True).items():
        setattr(db_config, field, value)
    db.commit()
    db.refresh(db_config)
    return db_config