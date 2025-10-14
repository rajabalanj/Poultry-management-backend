from sqlalchemy import Column, DateTime, String
from datetime import datetime
import pytz


class TimestampMixin:
    """Mixin that provides created/updated timestamps and user info.

    This is the minimal mixin used for most models. It does NOT include soft-delete
    columns so models can safely be deleted and recreated without unique-constraint
    collisions (e.g. inventory items keyed by name + tenant).
    """
    # Use timezone-aware timestamps to ensure all dates are stored in the desired timezone (Asia/Kolkata).
    # DateTime(timezone=True) ensures the timezone info is persisted in the database.
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)


class SoftDeleteMixin:
    """Mixin for soft-delete columns (deleted_at, deleted_by).

    Apply this only to models where soft-delete is absolutely necessary (audit trails,
    financial records, immutable historical data). Not all models should inherit this.
    """
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String, nullable=True)


class AuditMixin(TimestampMixin, SoftDeleteMixin):
    """Backward-compatible mixin combining timestamps + soft-delete.

    Existing models that already import `AuditMixin` will continue to work. New edits
    should prefer either `TimestampMixin` (no soft-delete) or explicitly add
    `SoftDeleteMixin` when soft-delete is required.
    """
    pass
