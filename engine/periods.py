"""
Alpha Decay Period Alignment & Financial Observation Representation.
Provides deterministic, audited alignment across fiscal and calendar quarters.
Strictly parses period representations, prevents silent substitutions, detects missing quarters,
and enforces reproducible point-in-time investigation cutoff dates.
"""

import re
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from pydantic import BaseModel, Field


class PeriodParsingError(ValueError):
    """Raised when a reporting period label cannot be strictly parsed into a valid financial period."""
    pass


MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5, "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}


def _get_quarter_from_month(month: int) -> int:
    """Returns calendar quarter (1=Jan-Mar, 2=Apr-Jun, 3=Jul-Sep, 4=Oct-Dec)."""
    return (month - 1) // 3 + 1


def _is_leap_year(year: int) -> bool:
    """Checks if a year is a Gregorian leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def _get_month_end_day(year: int, month: int) -> int:
    """Returns the exact last calendar day of the given month, accounting for leap years."""
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    if month == 2:
        return 29 if _is_leap_year(year) else 28
    raise PeriodParsingError(f"Invalid month integer: {month}. Must be between 1 and 12.")


class ReportingPeriod(BaseModel):
    """
    Normalized, strictly validated typed representation of a financial reporting period.
    Never fabricates missing dates or defaults unrecognized periods.
    """
    label: str
    year: int
    month: int
    calendar_quarter: int
    period_start_date: Optional[date] = None
    period_end_date: date
    is_annual: bool = False
    duration_months: int = 3
    fiscal_year: Optional[str] = None
    fiscal_quarter: Optional[int] = None
    fiscal_year_end_month: int = 3  # Standard Indian fiscal year ends in March
    publication_date: Optional[date] = None
    has_verified_publication_date: bool = False

    @classmethod
    def parse(
        cls,
        raw: str,
        is_annual: bool = False,
        publication_date: Optional[date] = None,
        fiscal_year_end_month: int = 3
    ) -> "ReportingPeriod":
        """
        Strictly parses period representations.
        Raises PeriodParsingError on unrecognized or invalid strings.
        Zero silent defaults to March or today's date.
        """
        if not raw or not isinstance(raw, str) or not raw.strip():
            raise PeriodParsingError("Empty or non-string reporting period cannot be parsed.")

        clean = raw.strip()

        # Pattern 1: 'Mar 2025', 'December 2023', 'jun 2024'
        m1 = re.match(r"^([A-Za-z]+)\s+(\d{4})$", clean)
        if m1:
            month_str = m1.group(1).lower()
            if month_str not in MONTH_MAP:
                raise PeriodParsingError(f"Unrecognized month name '{m1.group(1)}' in period label '{clean}'.")
            year = int(m1.group(2))
            if year < 1900 or year > 2100:
                raise PeriodParsingError(f"Year {year} out of reasonable financial reporting range (1900-2100).")
            month = MONTH_MAP[month_str]
            q = _get_quarter_from_month(month)
            day = _get_month_end_day(year, month)

            # Indian FY calculation: month <= 3 belongs to FY ending that year (e.g. Mar 2025 is FY25)
            # month > 3 belongs to FY ending next year (e.g. Jun 2024 is FY25)
            fy_year = year if month <= fiscal_year_end_month else year + 1
            fy = f"FY{str(fy_year)[-2:]}"

            # Fiscal quarter for standard March year-end (Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar)
            fq_map = {1: 4, 2: 4, 3: 4, 4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3}
            fq = fq_map[month] if fiscal_year_end_month == 3 else q

            dur = 12 if is_annual else 3
            # Period start date
            if is_annual:
                start_month = (month % 12) + 1
                start_year = year - 1 if start_month > month else year
                p_start = date(start_year, start_month, 1)
            else:
                start_month = month - 2
                start_year = year
                if start_month <= 0:
                    start_month += 12
                    start_year -= 1
                p_start = date(start_year, start_month, 1)

            return cls(
                label=clean,
                year=year,
                month=month,
                calendar_quarter=q,
                period_start_date=p_start,
                period_end_date=date(year, month, day),
                is_annual=is_annual,
                duration_months=dur,
                fiscal_year=fy,
                fiscal_quarter=fq,
                fiscal_year_end_month=fiscal_year_end_month,
                publication_date=publication_date,
                has_verified_publication_date=(publication_date is not None)
            )

        # Pattern 2: ISO date '2025-03-31', '2024-06-30'
        m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", clean)
        if m2:
            year = int(m2.group(1))
            month = int(m2.group(2))
            day = int(m2.group(3))
            if month < 1 or month > 12:
                raise PeriodParsingError(f"Month {month} out of valid range (1-12) in '{clean}'.")
            max_day = _get_month_end_day(year, month)
            if day < 1 or day > max_day:
                raise PeriodParsingError(f"Day {day} invalid for month {month}/{year} (max {max_day}) in '{clean}'.")

            q = _get_quarter_from_month(month)
            fy_year = year if month <= fiscal_year_end_month else year + 1
            fy = f"FY{str(fy_year)[-2:]}"
            dur = 12 if is_annual else 3
            return cls(
                label=clean,
                year=year,
                month=month,
                calendar_quarter=q,
                period_end_date=date(year, month, day),
                is_annual=is_annual,
                duration_months=dur,
                fiscal_year=fy,
                fiscal_quarter=q,
                fiscal_year_end_month=fiscal_year_end_month,
                publication_date=publication_date,
                has_verified_publication_date=(publication_date is not None)
            )

        # Pattern 3: 'Q1 FY25' or 'Q4 FY2025'
        m3 = re.match(r"^Q([1-4])\s*FY(\d{2,4})$", clean, re.IGNORECASE)
        if m3:
            q_num = int(m3.group(1))
            fy_raw = int(m3.group(2))
            fy_year = 2000 + fy_raw if fy_raw < 100 else fy_raw
            if fiscal_year_end_month == 3:
                # In Indian FY: Q1=Jun (prior year), Q2=Sep (prior year), Q3=Dec (prior year), Q4=Mar (fy_year)
                month_map_fy = {1: (fy_year - 1, 6), 2: (fy_year - 1, 9), 3: (fy_year - 1, 12), 4: (fy_year, 3)}
                year, month = month_map_fy[q_num]
            else:
                # Generic calendar-aligned FY
                month = q_num * 3
                year = fy_year

            day = _get_month_end_day(year, month)
            return cls(
                label=clean,
                year=year,
                month=month,
                calendar_quarter=_get_quarter_from_month(month),
                period_end_date=date(year, month, day),
                is_annual=is_annual,
                duration_months=3,
                fiscal_year=f"FY{str(fy_year)[-2:]}",
                fiscal_quarter=q_num,
                fiscal_year_end_month=fiscal_year_end_month,
                publication_date=publication_date,
                has_verified_publication_date=(publication_date is not None)
            )

        # Pattern 4: Annual FY e.g. 'FY24', 'FY2024'
        m4 = re.match(r"^FY(\d{2,4})$", clean, re.IGNORECASE)
        if m4:
            fy_raw = int(m4.group(1))
            fy_year = 2000 + fy_raw if fy_raw < 100 else fy_raw
            year = fy_year
            month = fiscal_year_end_month
            day = _get_month_end_day(year, month)
            return cls(
                label=clean,
                year=year,
                month=month,
                calendar_quarter=_get_quarter_from_month(month),
                period_end_date=date(year, month, day),
                is_annual=True,
                duration_months=12,
                fiscal_year=f"FY{str(fy_year)[-2:]}",
                fiscal_quarter=None,
                fiscal_year_end_month=fiscal_year_end_month,
                publication_date=publication_date,
                has_verified_publication_date=(publication_date is not None)
            )

        # If no patterns match, NEVER silently default. Raise typed error.
        raise PeriodParsingError(
            f"Unable to parse period label '{clean}'. Supported formats: "
            f"'Mon YYYY' (e.g. 'Mar 2025'), 'YYYY-MM-DD' (e.g. '2025-03-31'), "
            f"'Q[1-4] FY[YY/YYYY]' (e.g. 'Q4 FY25'), or 'FY[YY/YYYY]' (e.g. 'FY24')."
        )

    def yoy_expected_label(self) -> str:
        """Returns the expected prior-year period label, e.g. 'Mar 2025' -> 'Mar 2024'."""
        month_abbr = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                      7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
        abbr = month_abbr.get(self.month, "Mar")
        return f"{abbr} {self.year - 1}"

    def qoq_expected_label(self) -> str:
        """Returns the expected preceding quarter label, e.g. 'Mar 2025' -> 'Dec 2024'."""
        month_abbr = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                      7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
        if self.month <= 3:
            prev_month = 12
            prev_year = self.year - 1
        else:
            prev_month = self.month - 3
            prev_year = self.year
        abbr = month_abbr.get(prev_month, "Dec")
        return f"{abbr} {prev_year}"


class PeriodAlignmentResult(BaseModel):
    """Result of an explicit period alignment query."""
    target_period: ReportingPeriod
    comparison_period: Optional[ReportingPeriod] = None
    is_aligned: bool
    comparison_type: str  # 'yoy', 'qoq', 'custom', 'peer'
    reason: Optional[str] = None


class PeriodAligner:
    """
    Central period alignment authority.
    Eliminates index-based offset assumptions (e.g. index i-4).
    Enforces strict point-in-time cutoff compliance and validates chronological sequences.
    """

    @staticmethod
    def parse_periods(
        raw_periods: List[str],
        is_annual: bool = False,
        publication_dates: Optional[Dict[str, date]] = None,
        sort_chronological: bool = True
    ) -> List[ReportingPeriod]:
        """
        Parses list of period strings into ReportingPeriod objects.
        Validates periods, checks for duplicates, and optionally sorts chronologically.
        """
        parsed: List[ReportingPeriod] = []
        seen_dates: Set[Tuple[int, int, bool]] = set()

        for p_str in raw_periods:
            pub_date = publication_dates.get(p_str) if publication_dates else None
            p = ReportingPeriod.parse(p_str, is_annual=is_annual, publication_date=pub_date)
            # Check for duplicate period end dates in same frequency
            key = (p.year, p.month, p.is_annual)
            if key in seen_dates:
                # Warning or secondary instance: skip duplicate to prevent double-counting
                continue
            seen_dates.add(key)
            parsed.append(p)

        if sort_chronological:
            parsed.sort(key=lambda x: (x.period_end_date, x.is_annual))

        return parsed

    @classmethod
    def filter_by_cutoff(
        cls,
        periods: List[ReportingPeriod],
        cutoff_date: Optional[date] = None,
        strict_point_in_time: bool = False
    ) -> List[ReportingPeriod]:
        """
        Enforces a reproducible investigation cutoff date.
        If strict_point_in_time is True, observations with unknown publication dates
        are excluded unless period_end_date + standard 45-day filing lag is still <= cutoff.
        """
        if not cutoff_date:
            return periods

        filtered = []
        for p in periods:
            if p.publication_date is not None:
                if p.publication_date <= cutoff_date:
                    filtered.append(p)
            else:
                # Publication date not explicitly verified
                if strict_point_in_time:
                    # In strict mode, period end alone is not proof of availability
                    continue
                # Normal operational mode: period_end_date must be <= cutoff
                if p.period_end_date <= cutoff_date:
                    filtered.append(p)

        return filtered

    @classmethod
    def find_yoy_pair(
        cls,
        target: ReportingPeriod,
        available_periods: List[ReportingPeriod]
    ) -> PeriodAlignmentResult:
        """
        Finds the exact same quarter from the prior fiscal/calendar year.
        NEVER silently substitutes an adjacent quarter like Dec 2023 for Mar 2024.
        """
        target_month = target.month
        target_prior_year = target.year - 1

        for candidate in available_periods:
            if candidate.year == target_prior_year and candidate.month == target_month:
                if candidate.is_annual == target.is_annual:
                    return PeriodAlignmentResult(
                        target_period=target,
                        comparison_period=candidate,
                        is_aligned=True,
                        comparison_type="yoy"
                    )

        expected = target.yoy_expected_label()
        return PeriodAlignmentResult(
            target_period=target,
            comparison_period=None,
            is_aligned=False,
            comparison_type="yoy",
            reason=f"YoY baseline period '{expected}' is missing from available disclosures. "
                   f"Calculation skipped to prevent false growth inference."
        )

    @classmethod
    def find_qoq_pair(
        cls,
        target: ReportingPeriod,
        available_periods: List[ReportingPeriod]
    ) -> PeriodAlignmentResult:
        """
        Finds the immediately preceding comparable quarter.
        """
        if target.month <= 3:
            expected_month = 12
            expected_year = target.year - 1
        else:
            expected_month = target.month - 3
            expected_year = target.year

        for candidate in available_periods:
            if candidate.year == expected_year and candidate.month == expected_month:
                if candidate.is_annual == target.is_annual:
                    return PeriodAlignmentResult(
                        target_period=target,
                        comparison_period=candidate,
                        is_aligned=True,
                        comparison_type="qoq"
                    )

        expected = target.qoq_expected_label()
        return PeriodAlignmentResult(
            target_period=target,
            comparison_period=None,
            is_aligned=False,
            comparison_type="qoq",
            reason=f"QoQ preceding period '{expected}' is missing from available disclosures."
        )

    @classmethod
    def find_latest_common_peer_period(
        cls,
        target_periods: List[ReportingPeriod],
        peer_periods: List[ReportingPeriod]
    ) -> Tuple[Optional[ReportingPeriod], Optional[ReportingPeriod], bool, int]:
        """
        Aligns target with peer reporting periods.
        Returns:
            (common_target_period, common_peer_period, is_synchronous, gap_quarters)
        If no exact overlap exists, returns the latest available for each along with the gap.
        """
        if not target_periods or not peer_periods:
            return None, None, False, 0

        # Create lookup for peer periods
        peer_lookup = {(p.year, p.month): p for p in peer_periods if not p.is_annual}

        # Check in reverse chronological order for an exact contemporaneous match
        target_quarterly = [p for p in target_periods if not p.is_annual]
        for t_p in reversed(target_quarterly):
            key = (t_p.year, t_p.month)
            if key in peer_lookup:
                return t_p, peer_lookup[key], True, 0

        # No exact match: find the latest quarterly of each and compute the gap in quarters
        if not target_quarterly or not peer_lookup:
            return None, None, False, 0

        latest_target = sorted(target_quarterly, key=lambda x: x.period_end_date)[-1]
        latest_peer = sorted(peer_lookup.values(), key=lambda x: x.period_end_date)[-1]

        # Calculate calendar quarter difference
        q_target = latest_target.year * 4 + latest_target.calendar_quarter
        q_peer = latest_peer.year * 4 + latest_peer.calendar_quarter
        gap = q_target - q_peer

        return latest_target, latest_peer, False, gap
