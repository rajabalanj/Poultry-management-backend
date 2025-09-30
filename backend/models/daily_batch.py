from sqlalchemy import Column, Integer, String, Date, ForeignKey, func
from sqlalchemy.orm import relationship
from database import Base
from datetime import date
from sqlalchemy.ext.hybrid import hybrid_property
from models.bovanswhitelayerperformance import BovansWhiteLayerPerformance
from sqlalchemy.orm import object_session
from models.composition_usage_history import CompositionUsageHistory
from models.inventory_items import InventoryItem
from decimal import Decimal


class DailyBatch(Base):
    __tablename__ = "daily_batch"
    batch_id = Column(Integer, ForeignKey("batch.id"), primary_key=True)
    tenant_id = Column(String, index=True)
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
    
    @property
    def standard_feed_in_grams(self):
        session = object_session(self)
        bovans_performance = session.query(BovansWhiteLayerPerformance).filter(
            BovansWhiteLayerPerformance.age_weeks == int(float(self.age)) + 1
        ).first()
        # This will return the standard feed per bird. 
        # You might need to multiply this by closing_count in the frontend 
        # or in another property to get the total standard feed for the flock.
        return bovans_performance.feed_intake_per_day_g if bovans_performance else None

    @property
    def standard_feed_in_kg(self):
        if self.standard_feed_in_grams:
            return self.standard_feed_in_grams / 1000
        return None

    @hybrid_property
    def batch_type(self):
        if float(self.age) < 16:
            return 'Chick'
        elif float(self.age) <= 18:  # include 18 in this range
            return 'Grower'
        elif float(self.age) > 18:
            return 'Layer'
        
    @property
    def feed_in_grams(self):
        session = object_session(self)
        if not session:
            return 0

        total_feed_kg = Decimal(0)
        
        usages = session.query(CompositionUsageHistory).filter(
            CompositionUsageHistory.batch_id == self.batch_id,
            func.date(CompositionUsageHistory.used_at) == self.batch_date
        ).all()

        for usage in usages:
            for item_in_comp in usage.composition_items:
                item = session.query(InventoryItem).filter(InventoryItem.id == item_in_comp['inventory_item_id']).first()
                if item and item.category == 'Feed':
                    total_feed_kg += Decimal(str(item_in_comp['weight'])) * Decimal(usage.times)

        return float(total_feed_kg * 1000)

    @property
    def feed_in_kg(self):
        return self.feed_in_grams / 1000 if self.feed_in_grams is not None else 0
