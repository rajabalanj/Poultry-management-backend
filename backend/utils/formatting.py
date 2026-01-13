from decimal import Decimal

def format_indian_currency(amount: Decimal) -> str:
    if amount is None:
        return "₹ 0.00"
    amount = Decimal(amount)
    amount_str = f"{amount:.2f}"
    if "." in amount_str:
        integer_part, decimal_part = amount_str.split(".")
    else:
        integer_part, decimal_part = amount_str, "00"
    
    if len(integer_part) <= 3:
        return f"₹ {integer_part}.{decimal_part}"
    
    last_three = integer_part[-3:]
    remaining = integer_part[:-3]
    
    formatted_remaining = ""
    while len(remaining) > 2:
        formatted_remaining = "," + remaining[-2:] + formatted_remaining
        remaining = remaining[:-2]
    
    formatted_remaining = remaining + formatted_remaining
    
    return f"₹ {formatted_remaining},{last_three}.{decimal_part}"

def amount_to_words(n: Decimal) -> str:
    if n is None:
        return ""
    n = float(n)
    if n < 0:
        return "Minus " + amount_to_words(-n)
    if n == 0:
        return "Zero"
    
    units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def convert(num):
        if num < 20:
            return units[int(num)]
        elif num < 100:
            return tens[int(num // 10)] + (" " + units[int(num % 10)] if num % 10 != 0 else "")
        elif num < 1000:
            return units[int(num // 100)] + " Hundred" + (" " + convert(num % 100) if num % 100 != 0 else "")
        elif num < 100000:
            return convert(num // 1000) + " Thousand" + (" " + convert(num % 1000) if num % 1000 != 0 else "")
        elif num < 10000000:
            return convert(num // 100000) + " Lakh" + (" " + convert(num % 100000) if num % 100000 != 0 else "")
        else:
            return convert(num // 10000000) + " Crore" + (" " + convert(num % 10000000) if num % 10000000 != 0 else "")

    integer_part = int(n)
    decimal_part = int(round((n - integer_part) * 100))
    
    result = convert(integer_part)
    
    if decimal_part > 0:
        result += " and " + convert(decimal_part) + " Paise"
        
    return result