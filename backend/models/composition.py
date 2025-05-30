from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database import Base

class Composition(Base):
    __tablename__ = "composition"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    feeds = relationship("FeedInComposition", cascade="all, delete-orphan", backref="composition")