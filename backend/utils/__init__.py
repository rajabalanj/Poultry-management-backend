from sqlalchemy.orm import class_mapper
from .age_utils import calculate_age_progression

def sqlalchemy_to_dict(obj):
    """Convert a SQLAlchemy object to a dictionary."""
    if not obj:
        return None
    mapper = class_mapper(obj.__class__)
    result = {}
    for c in mapper.columns:
        value = getattr(obj, c.key)
        # Convert datetime objects to ISO format strings
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        # Convert Decimal objects to floats
        elif hasattr(value, 'normalize') and hasattr(value, 'from_float'):  # Check if it's a Decimal
            value = float(value)
        # Convert enum types to strings
        elif hasattr(value, 'name'):  # Check if it's an enum
            value = value.name
        result[c.key] = value
    return result

__all__ = ['calculate_age_progression', 'sqlalchemy_to_dict']