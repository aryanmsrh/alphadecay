import pytest
from datetime import date
from engine.periods import ReportingPeriod, PeriodAligner, PeriodParsingError

def test_parse_periods():
    p1 = ReportingPeriod.parse("Mar 2025")
    assert p1.year == 2025
    assert p1.month == 3
    assert p1.calendar_quarter == 1
    assert p1.period_end_date == date(2025, 3, 31)
    assert p1.yoy_expected_label() == "Mar 2024"
    assert p1.qoq_expected_label() == "Dec 2024"

    p2 = ReportingPeriod.parse("Jun 2024")
    assert p2.year == 2024
    assert p2.month == 6
    assert p2.calendar_quarter == 2
    assert p2.period_end_date == date(2024, 6, 30)
    assert p2.yoy_expected_label() == "Jun 2023"
    assert p2.qoq_expected_label() == "Mar 2024"

def test_strict_parsing_rejects_unrecognized_or_invalid():
    # Unknown month name
    with pytest.raises(PeriodParsingError) as exc:
        ReportingPeriod.parse("Foo 2025")
    assert "Unrecognized month name" in str(exc.value)

    # Empty string
    with pytest.raises(PeriodParsingError):
        ReportingPeriod.parse("")

    # Random string
    with pytest.raises(PeriodParsingError):
        ReportingPeriod.parse("not-a-period")

    # Invalid day in ISO
    with pytest.raises(PeriodParsingError):
        ReportingPeriod.parse("2023-02-29")  # 2023 is not a leap year

    # Valid leap day
    p_leap = ReportingPeriod.parse("2024-02-29")
    assert p_leap.period_end_date == date(2024, 2, 29)

def test_yoy_alignment_success():
    raw_periods = ["Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"]
    parsed = PeriodAligner.parse_periods(raw_periods)
    target = parsed[-1] # Mar 2025
    
    result = PeriodAligner.find_yoy_pair(target, parsed)
    assert result.is_aligned is True
    assert result.comparison_period is not None
    assert result.comparison_period.label == "Mar 2024"

def test_march_2025_vs_dec_2023_regression_defect():
    """
    REGRESSION TEST:
    Verify that when March 2024 is missing from disclosures (e.g. Screener Nestlé India dataset:
    ['Dec 2023', 'Jun 2024', 'Sep 2024', 'Dec 2024', 'Mar 2025']),
    March 2025 is NOT matched with December 2023.
    The alignment must explicitly reject the pair.
    """
    raw_periods = ["Dec 2023", "Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"]
    parsed = PeriodAligner.parse_periods(raw_periods)
    target = parsed[-1] # Mar 2025 (index 4)
    
    # Old logic: index 4 - 4 = 0 -> Dec 2023 (WRONG)
    old_flawed_match = parsed[0].label # "Dec 2023"
    
    result = PeriodAligner.find_yoy_pair(target, parsed)
    assert result.is_aligned is False
    assert result.comparison_period is None
    assert "Mar 2024" in result.reason
    assert "missing" in result.reason.lower()
    
    # Verify Dec 2023 was NOT selected
    if result.comparison_period:
        assert result.comparison_period.label != old_flawed_match

def test_peer_synchronization_and_mismatch_detection():
    # Target has Sep 2026 data
    target_periods = PeriodAligner.parse_periods(["Mar 2026", "Jun 2026", "Sep 2026"])
    # Peer only has up to Jun 2026 data
    peer_periods = PeriodAligner.parse_periods(["Dec 2025", "Mar 2026", "Jun 2026"])
    
    # Common latest period is Jun 2026
    c_target, c_peer, is_sync, gap = PeriodAligner.find_latest_common_peer_period(target_periods, peer_periods)
    assert is_sync is True
    assert c_target.label == "Jun 2026"
    assert c_peer.label == "Jun 2026"
    assert gap == 0

    # Non-overlapping case
    target_periods_future = PeriodAligner.parse_periods(["Sep 2026"])
    peer_periods_past = PeriodAligner.parse_periods(["Jun 2026"])
    c_target, c_peer, is_sync, gap = PeriodAligner.find_latest_common_peer_period(target_periods_future, peer_periods_past)
    assert is_sync is False
    assert gap == 1 # 1 quarter ahead

def test_investigation_cutoff_enforcement():
    raw_periods = ["Mar 2025", "Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026"]
    parsed = PeriodAligner.parse_periods(raw_periods)
    
    # Cutoff at 2025-10-01 (should exclude Dec 2025 and Mar 2026)
    cutoff = date(2025, 10, 1)
    filtered = PeriodAligner.filter_by_cutoff(parsed, cutoff_date=cutoff)
    labels = [p.label for p in filtered]
    assert labels == ["Mar 2025", "Jun 2025", "Sep 2025"]
    assert "Dec 2025" not in labels
    assert "Mar 2026" not in labels

def test_investigation_cutoff_strict_point_in_time():
    # Without publication date in strict mode, observation with unverified publication date is excluded
    p_unverified = ReportingPeriod.parse("Mar 2025")
    p_verified = ReportingPeriod.parse("Mar 2025", publication_date=date(2025, 5, 1))

    cutoff = date(2025, 5, 15)
    # Strict mode
    filtered_strict = PeriodAligner.filter_by_cutoff([p_unverified, p_verified], cutoff_date=cutoff, strict_point_in_time=True)
    assert len(filtered_strict) == 1
    assert filtered_strict[0].publication_date == date(2025, 5, 1)

    # Post-cutoff verified publication date is excluded
    p_published_late = ReportingPeriod.parse("Dec 2024", publication_date=date(2025, 6, 1))
    filtered_late = PeriodAligner.filter_by_cutoff([p_published_late], cutoff_date=cutoff, strict_point_in_time=True)
    assert len(filtered_late) == 0
