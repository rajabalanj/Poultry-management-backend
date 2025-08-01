from sqlalchemy import Column, Integer, String, Date, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import relationship
from database import Base
from datetime import date
from sqlalchemy.ext.hybrid import hybrid_property
from models.bovanswhitelayerperformance import BovansWhiteLayerPerformance
from sqlalchemy.orm import object_session


class DailyBatch(Base):
    __tablename__ = "daily_batch"
    batch_id = Column(Integer, ForeignKey("batch.id"), primary_key=True)
    batch = relationship("Batch", back_populates="daily_batches")
    shed_no = Column(String)
    batch_no = Column(String)
    upload_date = Column(Date, default=date.today)
    batch_date = Column(Date, default=date.today, primary_key=True)
    age = Column(String)
    opening_count = Column(Integer)
    mortality = Column(Integer, default=0)
    culls = Column(Integer, default=0)
    table_eggs = Column(Integer, default=0)
    jumbo = Column(Integer, default=0)
    cr = Column(Integer, default=0)
    notes = Column(String, nullable=True)


    @hybrid_property
    def total_eggs(self):
        return self.table_eggs + self.jumbo + self.cr
    
    @hybrid_property
    def closing_count(self):
        return self.opening_count - (self.mortality + self.culls)
    
    @hybrid_property
    def hd(self):
        return self.total_eggs / self.closing_count if self.closing_count > 0 else 0
    
    @property
    def standard_hen_day_percentage(self):
        session = object_session(self)
        bovans_performance = session.query(BovansWhiteLayerPerformance).filter(
            BovansWhiteLayerPerformance.age_weeks == int(float(self.age)) + 1
        ).first()
        return bovans_performance.lay_percent if bovans_performance else None
    
    @hybrid_property
    def batch_type(self):
        if float(self.age) < 16:
            return 'Chick'
        elif float(self.age) <= 18:  # include 18 in this range
            return 'Grower'
        elif float(self.age) > 18:
            return 'Layer'
        

