from sqlalchemy.orm import class_mapper
from .age_utils import calculate_age_progression

def sqlalchemy_to_dict(obj):
    """Convert a SQLAlchemy object to a dictionary."""
    if not obj:
        return None
    mapper = class_mapper(obj.__class__)
    return {c.key: getattr(obj, c.key) for c in mapper.columns}

__all__ = ['calculate_age_progression', 'sqlalchemy_to_dict']