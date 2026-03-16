from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, case, cast, Date, Numeric
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from models.bovanswhitelayerperformance import BovansWhiteLayerPerformance
from models.bv300_layer_performance import BV300LayerPerformance
from models.bv300_rearing_performance import BV300RearingPerformance
from models.app_config import AppConfig
from sqlalchemy.orm import object_session
from models.composition_usage_history import CompositionUsageHistory
from models.inventory_items import InventoryItem
from decimal import Decimal
from models.audit_mixin import TimestampMixin
import pytz


def _get_standard_source(session, tenant_id):
    if not tenant_id or not session:
        return "bovans"
    config = session.query(AppConfig).filter(
        AppConfig.tenant_id == tenant_id,
        AppConfig.name == "performance_standard_source"
    ).first()
    if not config or not config.value:
        return "bovans"

    normalized = config.value.strip().lower().replace('-', '').replace('_', '')
    if normalized == "bv300":
        return "bv300"

    if normalized == "bovans":
        return "bovans"

    return "bovans"


def _get_standard_lookup_age(age_in_weeks, source):
    if age_in_weeks is None:
        return None

    try:
        age_in_weeks = int(age_in_weeks)
    except (ValueError, TypeError):
        return None

    if source == "bv300":
        if age_in_weeks < 1:
            age_in_weeks = 1
        # Rearing covers week 1-18, layer covers week 19-80
        if age_in_weeks < 18:
            lookup_age = age_in_weeks + 1
            return min(max(lookup_age, 1), 18)
        else:
            lookup_age = age_in_weeks + 1
            return min(max(lookup_age, 19), 80)

    # Default Bovans behavior
    lookup_age = age_in_weeks + 1
    if lookup_age < 1:
        lookup_age = 1
    return min(lookup_age, 100)


def _get_standard_performance(session, tenant_id, age_weeks):
    source = _get_standard_source(session, tenant_id)
    if age_weeks is None:
        return None

    if source == "bv300":
        if age_weeks < 19:
            model = BV300RearingPerformance
            age_weeks = min(max(age_weeks, 1), 18)
        else:
            model = BV300LayerPerformance
            age_weeks = min(max(age_weeks, 19), 80)
    else:
        model = BovansWhiteLayerPerformance
        age_weeks = min(max(age_weeks, 1), 100)

    return session.query(model).filter(
        model.age_weeks == age_weeks,
        model.tenant_id == tenant_id
    ).first()


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
    age = Column(Numeric(4, 1))
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
        if not session:
            return None

        try:
            age_in_weeks = int(self.age)
        except (ValueError, TypeError):
            return None

        source = _get_standard_source(session, self.tenant_id)
        # bv300 rearing has no lay_percent — only layer phase does
        if source == "bv300" and age_in_weeks < 18:
            return None

        lookup_age = _get_standard_lookup_age(age_in_weeks, source)
        standard_performance = _get_standard_performance(session, self.tenant_id, lookup_age)

        if not standard_performance:
            return None

        if hasattr(standard_performance, "lay_percent"):
            return standard_performance.lay_percent

        return None

    @standard_hen_day_percentage.expression
    def standard_hen_day_percentage(cls):
        from sqlalchemy import select, Integer, case, cast, func

        source_expr = select(func.coalesce(AppConfig.value, 'bovans')).where(
            AppConfig.tenant_id == cls.tenant_id,
            AppConfig.name == 'performance_standard_source'
        ).scalar_subquery()
        normalized_source = func.replace(func.replace(func.lower(source_expr), '_', ''), '-', '')
        standard_source = case(
            (normalized_source == 'bv300', 'bv300'),
            (normalized_source == 'bovans', 'bovans'),
            else_='bovans'
        )

        age_in_weeks_expr = cast(cls.age, Integer)
        bovans_lookup_age = case(
            (age_in_weeks_expr < 1, 1),
            (age_in_weeks_expr >= 100, 100),
            else_=age_in_weeks_expr + 1
        )
        bv300_lookup_age = case(
            (age_in_weeks_expr < 1, 1),
            (age_in_weeks_expr < 18, (age_in_weeks_expr + 1)),
            else_=(age_in_weeks_expr + 1)
        )
        bv300_lookup_age = case(
            (age_in_weeks_expr < 18, case((age_in_weeks_expr < 1, 1), else_=age_in_weeks_expr + 1)),
            else_=case((age_in_weeks_expr < 19, 19), else_=case((age_in_weeks_expr > 80, 80), else_=age_in_weeks_expr + 1))
        )

        lookup_age_expr = case(
            (standard_source == 'bv300', bv300_lookup_age),
            else_=bovans_lookup_age
        )

        bv300_rearing_lay = select(BV300RearingPerformance.lay_percent).where(
            BV300RearingPerformance.age_weeks == lookup_age_expr,
            BV300RearingPerformance.tenant_id == cls.tenant_id
        ).limit(1).scalar_subquery()

        bv300_layer_lay = select(BV300LayerPerformance.lay_percent).where(
            BV300LayerPerformance.age_weeks == lookup_age_expr,
            BV300LayerPerformance.tenant_id == cls.tenant_id
        ).limit(1).scalar_subquery()

        bovans_lay = select(BovansWhiteLayerPerformance.lay_percent).where(
            BovansWhiteLayerPerformance.age_weeks == lookup_age_expr,
            BovansWhiteLayerPerformance.tenant_id == cls.tenant_id
        ).limit(1).scalar_subquery()

        bv300_lay = case((lookup_age_expr <= 18, bv300_rearing_lay), else_=bv300_layer_lay)

        return case(
            (standard_source == 'bv300', bv300_lay),
            else_=bovans_lay
        )
    
    @hybrid_property
    def standard_feed_in_grams(self):
        session = object_session(self)
        if not session:
            return None

        try:
            age_in_weeks = int(self.age)
        except (ValueError, TypeError):
            return None

        source = _get_standard_source(session, self.tenant_id)
        lookup_age = _get_standard_lookup_age(age_in_weeks, source)
        standard_performance = _get_standard_performance(session, self.tenant_id, lookup_age)

        if not standard_performance or not hasattr(standard_performance, "feed_intake_per_day_g"):
            return None

        return standard_performance.feed_intake_per_day_g

    @standard_feed_in_grams.expression
    def standard_feed_in_grams(cls):
        from sqlalchemy import select, case, cast, Integer, func

        source_expr = select(func.coalesce(AppConfig.value, 'bovans')).where(
            AppConfig.tenant_id == cls.tenant_id,
            AppConfig.name == 'performance_standard_source'
        ).scalar_subquery()
        normalized_source = func.replace(func.replace(func.lower(source_expr), '_', ''), '-', '')
        standard_source = case(
            (normalized_source == 'bv300', 'bv300'),
            (normalized_source == 'bovans', 'bovans'),
            else_='bovans'
        )

        age_in_weeks_expr = cast(cls.age, Integer)
        bovans_lookup_age = case(
            (age_in_weeks_expr < 1, 1),
            (age_in_weeks_expr >= 100, 100),
            else_=age_in_weeks_expr + 1
        )
        bv300_lookup_age = case(
            (age_in_weeks_expr < 1, 1),
            (age_in_weeks_expr < 18, age_in_weeks_expr + 1),
            else_=age_in_weeks_expr + 1
        )
        bv300_lookup_age = case(
            (age_in_weeks_expr < 18, case((age_in_weeks_expr < 1, 1), else_=age_in_weeks_expr + 1)),
            else_=case((age_in_weeks_expr < 19, 19), else_=case((age_in_weeks_expr > 80, 80), else_=age_in_weeks_expr + 1))
        )

        lookup_age_expr = case(
            (standard_source == 'bv300', bv300_lookup_age),
            else_=bovans_lookup_age
        )

        bv300_rearing_feed = select(BV300RearingPerformance.feed_intake_per_day_g).where(
            BV300RearingPerformance.age_weeks == lookup_age_expr,
            BV300RearingPerformance.tenant_id == cls.tenant_id
        ).limit(1).scalar_subquery()

        bv300_layer_feed = select(BV300LayerPerformance.feed_intake_per_day_g).where(
            BV300LayerPerformance.age_weeks == lookup_age_expr,
            BV300LayerPerformance.tenant_id == cls.tenant_id
        ).limit(1).scalar_subquery()

        bovans_feed = select(BovansWhiteLayerPerformance.feed_intake_per_day_g).where(
            BovansWhiteLayerPerformance.age_weeks == lookup_age_expr,
            BovansWhiteLayerPerformance.tenant_id == cls.tenant_id
        ).limit(1).scalar_subquery()

        bv300_feed = case((lookup_age_expr <= 18, bv300_rearing_feed), else_=bv300_layer_feed)

        return case(
            (standard_source == 'bv300', bv300_feed),
            else_=bovans_feed
        )

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
        if self.age < 8:
            return 'Chick'
        elif self.age <= 17:
            return 'Grower'
        elif self.age > 17:
            return 'Layer'
        
    @batch_type.expression
    def batch_type(cls):
        return case(
            (cls.age < 8, 'Chick'),
            (cls.age <= 17, 'Grower'),
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

    @feed_in_grams.expression
    def feed_in_grams(cls):
        # Import the CompositionUsageItem model
        from models.composition_usage_item import CompositionUsageItem

        # Create a subquery to calculate the feed in grams
        from sqlalchemy import select, and_

        # Subquery to get the total feed in kg for each batch/date combination
        subquery = select(
            CompositionUsageHistory.batch_id,
            func.date(CompositionUsageHistory.used_at).label('batch_date'),
            func.sum(
                case(
                    (CompositionUsageItem.item_category == 'Feed', CompositionUsageItem.weight * CompositionUsageHistory.times),
                    else_=0
                )
            ).label('total_feed_kg')
        ).join(
            CompositionUsageHistory.items
        ).group_by(
            CompositionUsageHistory.batch_id,
            func.date(CompositionUsageHistory.used_at)
        ).subquery()

        # Join with DailyBatch and convert to grams
        return case(
            (
                and_(
                    cls.batch_id == subquery.c.batch_id,
                    cls.batch_date == subquery.c.batch_date
                ),
                subquery.c.total_feed_kg * 1000
            ),
            else_=0
        )


    @hybrid_property
    def feed_in_kg(self):
        return self.feed_in_grams / 1000 if self.feed_in_grams is not None else 0
    
    @feed_in_kg.expression
    def feed_in_kg(cls):
        return case(
            (cls.feed_in_grams.isnot(None), cls.feed_in_grams / 1000),
            else_=0
        )
