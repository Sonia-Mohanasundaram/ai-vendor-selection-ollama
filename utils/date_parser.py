"""
date_parser.py
--------------
Lightweight date and duration parsing utilities.
"""

import re
from datetime import datetime, date
from typing import Optional


# Common date formats to try
DATE_FORMATS = [
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%Y/%m/%d", "%Y-%m-%d",
    "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y",
]


def parse_date(date_str: str) -> Optional[date]:
    """
    Parse a date string using multiple format attempts.

    Args:
        date_str: Raw date string

    Returns:
        datetime.date or None if unparseable
    """
    date_str = date_str.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def days_until(target: date) -> int:
    """Return the number of days from today until a target date."""
    delta = target - date.today()
    return max(0, delta.days)


def parse_duration_to_days(text: str) -> Optional[int]:
    """
    Parse a natural-language duration string to an integer number of days.

    Examples:
        "14 days"   → 14
        "2 weeks"   → 14
        "1 month"   → 30

    Args:
        text: Raw string containing a duration

    Returns:
        int (days) or None if not parseable
    """
    text = text.lower().strip()

    match = re.search(r"(\d+)\s*(day|days|week|weeks|month|months)", text)
    if match:
        value = int(match.group(1))
        unit  = match.group(2)
        if unit.startswith("day"):
            return value
        elif unit.startswith("week"):
            return value * 7
        elif unit.startswith("month"):
            return value * 30
    return None


def parse_payment_terms_to_days(text: str) -> Optional[int]:
    """
    Convert common payment terms text to days.

    Examples:
        "Net 30" -> 30
        "Immediate" -> 1
        "Advance" -> 0
        "Within 45 days" -> 45
    """
    if not text:
        return None
    t = text.lower().strip()

    if re.search(r"\badvance\b|\bupfront\b", t):
        return 0
    if re.search(r"\bimmediate\b|\bon\s*delivery\b|\bpayable\s*immediately\b", t):
        return 1

    m = re.search(r"\bnet\s*(\d+)\b", t)
    if m:
        return int(m.group(1))

    m = re.search(r"\bwithin\s*(\d+)\s*days?\b", t)
    if m:
        return int(m.group(1))

    m = re.search(r"(\d+)\s*days?", t)
    if m:
        return int(m.group(1))

    return parse_duration_to_days(t)


def parse_delivery_text_to_days(text: str) -> Optional[int]:
    """
    Convert delivery lead-time text to days.

    Examples:
        "2 weeks" -> 14
        "10 working days" -> 10
        "Immediate" -> 1
    """
    if not text:
        return None
    t = text.lower().strip()

    if re.search(r"\bimmediate\b|\bready\s*stock\b", t):
        return 1

    m = re.search(r"(\d+)\s*(working\s*days?|business\s*days?|days?)", t)
    if m:
        return int(m.group(1))

    m = re.search(r"(\d+)\s*weeks?", t)
    if m:
        return int(m.group(1)) * 7

    m = re.search(r"(\d+)\s*months?", t)
    if m:
        return int(m.group(1)) * 30

    return parse_duration_to_days(t)
