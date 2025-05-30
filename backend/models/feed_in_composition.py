from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class FeedInComposition(Base):
    __tablename__ = "feed_in_composition"
    id = Column(Integer, primary_key=True, index=True)
    composition_id = Column(Integer, ForeignKey("composition.id"))
    feed_id = Column(Integer, ForeignKey("feed.id"))
    weight = Column(Float, nullable=False)

    feed = relationship("Feed")