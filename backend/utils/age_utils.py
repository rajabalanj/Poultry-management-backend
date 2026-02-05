from decimal import Decimal

def calculate_age_progression(start_age: Decimal, days: int) -> Decimal:
    """
    Increment age by 0.1 per day. If decimal part is .7, add 0.4 instead of 0.1 to roll into new week.
    """
    current_age = start_age.quantize(Decimal('0.1'))
    for _ in range(days):
        decimal = current_age % 1
        if decimal == Decimal('0.7'):
            current_age += Decimal('0.4')
        else:
            current_age += Decimal('0.1')
    return current_age.quantize(Decimal('0.1'))
