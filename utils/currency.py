"""
currency.py
-----------
Currency utilities: symbol lookup and simple conversion helper.
"""

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
}

EXCHANGE_RATES_TO_INR = {
    "INR": 1.0,
    "USD": 83.0,
    "EUR": 90.0,
    "GBP": 105.0,
}


def symbol(currency_code: str) -> str:
    """Return the currency symbol for a given 3-letter code."""
    return CURRENCY_SYMBOLS.get(currency_code.upper(), currency_code)


def to_inr(amount: float, from_currency: str) -> float:
    """Convert an amount from the given currency to INR."""
    rate = EXCHANGE_RATES_TO_INR.get(from_currency.upper(), 1.0)
    return round(amount * rate, 2)


def format_inr(amount: float) -> str:
    """Format a float as an INR string with commas."""
    return f"₹{amount:,.2f}"
