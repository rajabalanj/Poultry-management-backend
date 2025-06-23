def calculate_age_progression(start_age: float, days: int) -> float:
    """
    Increment age by 0.1 per day. If decimal part is .7, add 0.4 instead of 0.1 to roll into new week.
    """
    current_age = round(start_age, 1)
    for _ in range(days):
        decimal = round(current_age % 1, 1)
        current_age = round(current_age + (0.4 if decimal == 0.7 else 0.1), 1)
    return current_age
