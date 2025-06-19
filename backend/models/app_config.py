from sqlalchemy import Column, Integer, Float
from database import Base

class AppConfig(Base):
    __tablename__ = "app_config"
    id = Column(Integer, primary_key=True, index=True)
    lowKgThreshold = Column(Float, nullable=False)
    lowTonThreshold = Column(Float, nullable=False)
    # Add more config fields as needed