from sqlalchemy import Column, Integer, String, Date
from database import Base
from datetime import date

class Feed(Base):
    __tablename__ = "feed"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, unique=True)
    quantity = Column(Integer)
    unit = Column(String)  # e.g., "kg", "tons"
    createdDate = Column(Date, default=date.today)
 
    