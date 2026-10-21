"""
Mathematical, formatting, and period-alignment tools for financial analytics.
Zero LLM dependencies.
"""
from typing import Any, Dict, List, Optional, Tuple
import re

MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def parse_period_key(period_str: str) -> Optional[Tuple[int, int]]:
    """Parses 'Mar 2024' into (2024, 3) tuple."""
    parts = period_str.strip().split()
    if len(parts) == 2:
        m_str = parts[0].lower()
        if m_str in MONTH_NAMES and parts[1].isdigit():
            return int(parts[1]), MONTH_NAMES[m_str]
    return None


def find_yoy_prior_period(
    target_period: str, all_periods: List[str]
) -> Optional[str]:
    """Finds the identical month quarter 1 year prior."""
    parsed = parse_period_key(target_period)
    if not parsed:
        return None
    target_year, target_month = parsed
    prior_year = target_year - 1
    for p in all_periods:
        p_parsed = parse_period_key(p)
        if p_parsed and p_parsed == (prior_year, target_month):
            return p
    return None


def calculate_percentage_growth(
    current: Optional[float], previous: Optional[float]
) -> Optional[float]:
    """Calculates YoY percentage growth: ((current - previous) / previous) * 100."""
    if current is None or previous is None or previous <= 0:
        return None
    return round(((current - previous) / previous) * 100.0, 2)


def calculate_operating_margin(
    operating_profit: Optional[float], revenue: Optional[float]
) -> Optional[float]:
    """Calculates operating profit margin: (operating_profit / revenue) * 100."""
    if operating_profit is None or revenue is None or revenue <= 0:
        return None
    return round((operating_profit / revenue) * 100.0, 2)


def coerce_float(val: Any) -> Optional[float]:
    """Coerces strings, integers, and floats into valid floats."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace(",", "").replace("%", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def normalize_row_key(key: str) -> str:
    """Normalizes row label for fuzzy matching."""
    return re.sub(r"[^a-zA-Z0-9]", "", key).lower()


def get_row_series(rows: Dict[str, List[Any]], keys: List[str]) -> List[Any]:
    """Retrieves series data for matching row names from scraped statements."""
    for k in keys:
        if k in rows and rows[k]:
            return rows[k]
    norm_rows = {normalize_row_key(rk): rvals for rk, rvals in rows.items() if rvals}
    for k in keys:
        norm_k = normalize_row_key(k)
        if norm_k in norm_rows:
            return norm_rows[norm_k]
    return []
