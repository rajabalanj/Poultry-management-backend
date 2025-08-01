from sqlalchemy import Column, Integer, String
from database import Base

class AppConfig(Base):
    __tablename__ = "app_config"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    value = Column(String(255), nullable=False)