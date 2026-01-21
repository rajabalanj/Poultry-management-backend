from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, case, cast, Float, Date
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from models.bovanswhitelayerperformance import BovansWhiteLayerPerformance
from sqlalchemy.orm import object_session
from models.composition_usage_history import CompositionUsageHistory
from models.inventory_items import InventoryItem
from decimal import Decimal
from models.audit_mixin import TimestampMixin
import pytz


class DailyBatch(Base, TimestampMixin):
    __tablename__ = "daily_batch"
    batch_id = Column(Integer, ForeignKey("batch.id"), primary_key=True)
    tenant_id = Column(String, primary_key=True, index=True)
    batch = relationship("Batch", back_populates="daily_batches")
    shed_id = Column(Integer, ForeignKey("sheds.id"), nullable=True)
    shed = relationship("Shed")
    batch_no = Column(String, nullable=True)
    upload_date = Column(Date, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')).date())
    batch_date = Column(Date, default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')).date(), primary_key=True)
    age = Column(String)
    opening_count = Column(Integer)
    mortality = Column(Integer, default=0)
    culls = Column(Integer, default=0)
    table_eggs = Column(Integer, default=0)
    jumbo = Column(Integer, default=0)
    cr = Column(Integer, default=0)
    notes = Column(String, nullable=True)
    birds_added = Column(Integer, default=0)

    @hybrid_property
    def total_eggs(self):
        return (self.table_eggs or 0) + (self.jumbo or 0) + (self.cr or 0)

    @total_eggs.expression
    def total_eggs(cls):
        return func.coalesce(cls.table_eggs, 0) + func.coalesce(cls.jumbo, 0) + func.coalesce(cls.cr, 0)

    @hybrid_property
    def closing_count(self):
        return (self.opening_count or 0) + (self.birds_added or 0) - ((self.mortality or 0) + (self.culls or 0))

    @closing_count.expression
    def closing_count(cls):
        return func.coalesce(cls.opening_count, 0) + func.coalesce(cls.birds_added, 0) - (func.coalesce(cls.mortality, 0) + func.coalesce(cls.culls, 0))

    @hybrid_property
    def hd(self):
        # For instance context, calculate directly using the instance values
        closing_count = self.opening_count + (self.birds_added or 0) - ((self.mortality or 0) + (self.culls or 0))
        if closing_count is not None and closing_count > 0:
            total_eggs = (self.table_eggs or 0) + (self.jumbo or 0) + (self.cr or 0)
            return total_eggs / closing_count
        return 0

    @hd.expression
    def hd(cls):
        return case(
            (cls.closing_count.isnot(None) & (cls.closing_count > 0), cls.total_eggs / cls.closing_count),
            else_=0
        )
    
    @hybrid_property
    def standard_hen_day_percentage(self):
        session = object_session(self)
        # self.age is "weeks.days" (e.g., "18.3"). int(18.3) gives 18 completed weeks.
        age_in_weeks = int(float(self.age))
        if age_in_weeks >= 100:
            lookup_age = 100
        else:
            # We add 1 to get the current week of life (e.g. 19th week for age 18.3) to match the standards table.
            lookup_age = age_in_weeks + 1

        bovans_performance = session.query(BovansWhiteLayerPerformance).filter(
            BovansWhiteLayerPerformance.age_weeks == lookup_age
        ).first()
        return bovans_performance.lay_percent if bovans_performance else None

    @standard_hen_day_percentage.expression
    def standard_hen_day_percentage(cls):
        # Create a subquery to get the lay_percent based on age
        from sqlalchemy import select, Integer, case, cast
        age_in_weeks_expr = cast(cls.age, Integer)
        lookup_age_expr = case((age_in_weeks_expr >= 100, 100), else_=age_in_weeks_expr + 1)
        subquery = select(BovansWhiteLayerPerformance.lay_percent).where(
            BovansWhiteLayerPerformance.age_weeks == lookup_age_expr
        ).limit(1).label('lay_percent')
        return subquery
    
    @hybrid_property
    def standard_feed_in_grams(self):
        session = object_session(self)
        # self.age is "weeks.days" (e.g., "18.3"). int(18.3) gives 18 completed weeks.
        age_in_weeks = int(float(self.age))
        if age_in_weeks >= 100:
            lookup_age = 100
        else:
            # We add 1 to get the current week of life (e.g. 19th week for age 18.3) to match the standards table.
            lookup_age = age_in_weeks + 1
        bovans_performance = session.query(BovansWhiteLayerPerformance).filter(
            BovansWhiteLayerPerformance.age_weeks == lookup_age
        ).first()
        # This will return the standard feed per bird. 
        # You might need to multiply this by closing_count in the frontend 
        # or in another property to get the total standard feed for the flock.
        return bovans_performance.feed_intake_per_day_g if bovans_performance else None

    @standard_feed_in_grams.expression
    def standard_feed_in_grams(cls):
        # Create a subquery to get the feed_intake_per_day_g based on age
        from sqlalchemy import select, case, cast, Integer
        age_in_weeks_expr = cast(cls.age, Integer)
        lookup_age_expr = case((age_in_weeks_expr >= 100, 100), else_=age_in_weeks_expr + 1)
        subquery = select(BovansWhiteLayerPerformance.feed_intake_per_day_g).where(
            BovansWhiteLayerPerformance.age_weeks == lookup_age_expr
        ).limit(1).label('feed_intake_per_day_g')
        return subquery

    @hybrid_property
    def standard_feed_in_kg(self):
        if self.standard_feed_in_grams is not None:
            return self.standard_feed_in_grams / 1000
        return None

    @standard_feed_in_kg.expression
    def standard_feed_in_kg(cls):
        return case(
            (cls.standard_feed_in_grams.isnot(None), cls.standard_feed_in_grams / 1000),
            else_=None
        )

    @hybrid_property
    def batch_type(self):
        if float(self.age) < 8:
            return 'Chick'
        elif float(self.age) <= 17:
            return 'Grower'
        elif float(self.age) > 17:
            return 'Layer'
        
    @batch_type.expression
    def batch_type(cls):
        return case(
            (cast(cls.age, Float) < 8, 'Chick'),
            (cast(cls.age, Float) <= 17, 'Grower'),
            else_='Layer'
        )
        
    @hybrid_property
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
            for item_in_comp in usage.items:
                if item_in_comp.item_category == 'Feed':
                    total_feed_kg += Decimal(str(item_in_comp.weight)) * Decimal(usage.times)

        return float(total_feed_kg * 1000)


    @hybrid_property
    def feed_in_kg(self):
        return self.feed_in_grams / 1000 if self.feed_in_grams is not None else 0
    
    @feed_in_kg.expression
    def feed_in_kg(cls):
        return case(
            (cls.feed_in_grams.isnot(None), cls.feed_in_grams / 1000),
            else_=0
        )