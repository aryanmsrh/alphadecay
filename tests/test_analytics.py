import pytest
from engine.analytics import FinancialAnalytics, FinancialObservation
from engine.forensics import ForensicEngine
from engine.periods import ReportingPeriod

def test_canonical_dsri_calculation():
    # Hand-calculated fixture:
    # Period t: AR = 120, Sales = 1000 -> Ratio_t = 0.12
    # Period t-1: AR = 100, Sales = 1000 -> Ratio_{t-1} = 0.10
    # Expected DSRI = 0.12 / 0.10 = 1.200
    dsri, err = FinancialAnalytics.compute_canonical_dsri(
        ar_t=120.0, sales_t=1000.0,
        ar_prev=100.0, sales_prev=1000.0
    )
    assert err is None
    assert dsri == 1.200

def test_canonical_dsri_differs_from_debtor_days_proxy():
    """
    REGRESSION & FIDELITY TEST:
    Demonstrate that statutory debtor days ratio (e.g. 5d / 4d = 1.25)
    is NOT interchangeable with the canonical DSRI.
    """
    # Suppose debtor days went from 4 to 5:
    dd_proxy, _ = FinancialAnalytics.compute_debtor_days_ratio_proxy(days_t=5.0, days_prev=4.0)
    assert dd_proxy == 1.250

    # But suppose Sales grew significantly:
    # Period t: AR = 100, Sales = 2000 -> Ratio_t = 0.05
    # Period t-1: AR = 80, Sales = 1000 -> Ratio_{t-1} = 0.08
    # Canonical DSRI = 0.05 / 0.08 = 0.625 (receivables intensity actually IMPROVED!)
    dsri, err = FinancialAnalytics.compute_canonical_dsri(
        ar_t=100.0, sales_t=2000.0,
        ar_prev=80.0, sales_prev=1000.0
    )
    assert err is None
    assert dsri == 0.625
    # The debtor days proxy (1.25) and canonical DSRI (0.625) move in completely different directions!
    assert dsri != dd_proxy

def test_canonical_dsri_edge_cases():
    # Zero sales current
    dsri, err = FinancialAnalytics.compute_canonical_dsri(ar_t=100.0, sales_t=0.0, ar_prev=100.0, sales_prev=1000.0)
    assert dsri is None
    assert "invalid denominator" in err.lower()

    # Zero sales prior
    dsri, err = FinancialAnalytics.compute_canonical_dsri(ar_t=100.0, sales_t=1000.0, ar_prev=100.0, sales_prev=0.0)
    assert dsri is None
    assert "invalid denominator" in err.lower()

    # Missing inputs
    dsri, err = FinancialAnalytics.compute_canonical_dsri(ar_t=None, sales_t=1000.0, ar_prev=100.0, sales_prev=1000.0)
    assert dsri is None
    assert "missing" in err.lower()

def test_incomplete_beneish_does_not_claim_complete_m_score():
    # Ingest partial quarterly data without COGS / Gross Margin
    res = FinancialAnalytics.compute_beneish_sub_indices(
        sales_t=5000.0, sales_prev=4500.0,
        opm_t=22.0, opm_prev=24.0,
        ar_t=300.0, ar_prev=250.0,
        debtor_days_t=18.0, debtor_days_prev=15.0
    )
    # Complete M-score must be False
    assert res.is_complete_m_score is False
    assert res.composite_m_score is None
    assert len(res.missing_components) > 0
    assert any("DEPI" in comp for comp in res.missing_components)
    assert res.dsri is not None
    assert res.sgi is not None
    # Canonical GMI must NOT be populated with OPM proxy!
    assert res.gmi is None
    # But OPM proxy should be available
    assert res.opm_margin_ratio_proxy == round(24.0 / 22.0, 3)

def test_canonical_gmi_calculation():
    # Canonical GMI = Prior Gross Margin / Current Gross Margin
    # Period t: Sales = 1000, COGS = 600 -> GM_t = 400/1000 = 0.40
    # Period t-1: Sales = 900, COGS = 450 -> GM_{t-1} = 450/900 = 0.50
    # GMI = 0.50 / 0.40 = 1.250 (Gross margins deteriorated)
    res = FinancialAnalytics.compute_beneish_sub_indices(
        sales_t=1000.0, sales_prev=900.0,
        cogs_t=600.0, cogs_prev=450.0,
        ar_t=100.0, ar_prev=90.0
    )
    assert res.gmi == 1.250

def test_aqi_does_not_default_to_one_on_zero_baseline():
    # When prior non-current assets is 0, AQI is undefined, not 1.0!
    res = FinancialAnalytics.compute_beneish_sub_indices(
        sales_t=1000.0, sales_prev=900.0,
        other_assets_t=50.0, total_assets_t=1000.0,
        other_assets_prev=0.0, total_assets_prev=900.0  # baseline ratio = 0
    )
    assert res.aqi is None
    assert any("AQI" in item for item in res.missing_components)

def test_expense_adjusted_residual_is_heuristic_not_volume():
    """
    Tests that expense residual is correctly computed but flagged as heuristic.
    """
    sales_g = 10.0
    exp_t = 800.0
    exp_prev = 700.0  # exp growth = (800-700)/700 = 14.2857%
    sales_t = 1000.0  # cost ratio = 0.8
    # exp effect = 14.2857% * 0.8 = 11.43%
    # residual = 10.0 - 11.43 = -1.43%
    residual, err = FinancialAnalytics.compute_expense_adjusted_residual(
        sales_growth_yoy=sales_g,
        expenses_t=exp_t,
        expenses_prev=exp_prev,
        sales_t=sales_t
    )
    assert err is None
    assert residual == -1.43

def test_zero_and_negative_growth_calculations():
    # Growth from 100 to 150 = 50%
    assert FinancialAnalytics.calculate_growth(150.0, 100.0) == 50.0
    # Growth from 100 to 50 = -50%
    assert FinancialAnalytics.calculate_growth(50.0, 100.0) == -50.0
    # Baseline <= 0 returns None
    assert FinancialAnalytics.calculate_growth(100.0, 0.0) is None
    assert FinancialAnalytics.calculate_growth(100.0, -50.0) is None
    # None input returns None
    assert FinancialAnalytics.calculate_growth(None, 100.0) is None

def test_genuine_no_anomaly_state():
    """
    Tests that ForensicEngine produces no_material_anomaly_detected = True
    and an empty anomalies list when all financial movements are within thresholds.
    """
    calm_raw_data = {
        "ticker": "CALMCO",
        "company_name": "Calm Consumer Co",
        "quarters": {
            "periods": ["Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
            "rows": {
                "Sales": [1000.0, 1005.0, 1010.0, 1015.0, 1020.0],
                "Expenses": [800.0, 804.0, 808.0, 812.0, 816.0],  # Constant 80% expense ratio
                "Operating Profit": [200.0, 201.0, 202.0, 203.0, 204.0],
                "OPM %": [20.0, 20.0, 20.0, 20.0, 20.0]  # Constant 20% margin
            }
        },
        "ratios_table": {
            "periods": ["Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
            "rows": {
                "Debtor Days": [15.0, 15.0, 15.0, 15.0, 15.5]  # Shift is only 0.5d (below 3.0d threshold)
            }
        },
        "cash_flow": {
            "rows": {
                "Cash from Operating Activity": [800.0]  # Healthy cash flow
            }
        }
    }
    summary = ForensicEngine.audit_company(calm_raw_data)
    assert summary.no_material_anomaly_detected is True
    assert len(summary.anomalies) == 0


def test_yoy_vs_qoq_independent_hand_calculation_and_mismatch_failure():
    """
    INDEPENDENT MATHEMATICAL & FIDELITY TEST:
    Verifies that expected values are independently hand-calculated,
    and proves that a test asserting YoY growth FAILS if the most recent quarter (QoQ)
    is erroneously used.
    """
    from engine.periods import PeriodAligner

    # Hand-calculated fixture:
    # Q4 FY24 (Mar 2024): 1300.0
    # Q1 FY25 (Jun 2024): 1350.0
    # Q2 FY25 (Sep 2024): 1380.0
    # Q3 FY25 (Dec 2024): 1400.0 (Sequential t-1)
    # Q4 FY25 (Mar 2025): 1600.0 (Target t)

    sales_q4_prev = 1300.0  # YoY baseline (Mar 2024)
    sales_q3_prev = 1400.0  # QoQ baseline (Dec 2024)
    sales_q4_curr = 1600.0  # Target (Mar 2025)

    # Independent hand calculation formulas:
    # YoY = (1600 - 1300) / 1300 * 100 = 300 / 1300 * 100 = 23.076923...% -> 23.08%
    expected_yoy_growth = round(((sales_q4_curr - sales_q4_prev) / sales_q4_prev) * 100.0, 2)
    assert expected_yoy_growth == 23.08

    # QoQ = (1600 - 1400) / 1400 * 100 = 200 / 1400 * 100 = 14.285714...% -> 14.29%
    expected_qoq_growth = round(((sales_q4_curr - sales_q3_prev) / sales_q3_prev) * 100.0, 2)
    assert expected_qoq_growth == 14.29

    # System calculation
    calc_yoy = FinancialAnalytics.calculate_growth(sales_q4_curr, sales_q4_prev)
    calc_qoq = FinancialAnalytics.calculate_growth(sales_q4_curr, sales_q3_prev)

    assert calc_yoy == expected_yoy_growth
    assert calc_qoq == expected_qoq_growth

    # PROVE MISMATCH: If YoY accidentally used sequential quarter (Dec 2024),
    # the result would be 14.29% instead of 23.08%, which is a substantial error.
    accidental_qoq_as_yoy = calc_qoq
    assert accidental_qoq_as_yoy != expected_yoy_growth
    assert abs(accidental_qoq_as_yoy - expected_yoy_growth) == pytest.approx(8.79, rel=1e-2)

    # Verify PeriodAligner guarantees separation of YoY and QoQ targets:
    periods = PeriodAligner.parse_periods(["Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"])
    target = periods[-1]  # Mar 2025

    yoy_align = PeriodAligner.find_yoy_pair(target, periods)
    qoq_align = PeriodAligner.find_qoq_pair(target, periods)

    assert yoy_align.is_aligned is True
    assert yoy_align.comparison_period.label == "Mar 2024"
    assert yoy_align.comparison_period.year == 2024
    assert yoy_align.comparison_period.month == 3

    assert qoq_align.is_aligned is True
    assert qoq_align.comparison_period.label == "Dec 2024"
    assert qoq_align.comparison_period.year == 2024
    assert qoq_align.comparison_period.month == 12

    # A YoY alignment must NEVER match the QoQ period
    assert yoy_align.comparison_period.label != qoq_align.comparison_period.label


def test_peer_failure_preserves_none_without_zero_substitution(mocker):
    """
    DATA INTEGRITY TEST:
    Verify that when peer fetching fails or data is unavailable:
    1. Peer spread days is strictly None, NEVER 0.0.
    2. Peer failures do not become zero-valued observations.
    """
    from agent.nodes import peer_triangulation_node

    # Mock peer fetcher to raise network exception
    mocker.patch(
        "agent.nodes.screener_scraper.fetch_company_data",
        side_effect=Exception("Connection refused by peer Screener endpoint")
    )

    state = {
        "ticker": "HINDUNILVR",
        "company_name": "Hindustan Unilever Ltd",
        "selected_anomaly": {
            "metric_name": "Debtor Days Compression & Collection Acceleration",
            "metric_type": "debtor_days",
            "delta": -4.0,
            "unit": "d",
            "period": "Mar 2026"
        },
        "computed_metrics": {},
        "logs": []
    }

    result = peer_triangulation_node(state)

    # Must be None, NEVER substituted with 0.0
    assert result["computed_metrics"]["peer_spread_days"] is None
    assert result["computed_metrics"]["peer_spread_days"] != 0.0
    assert len(result["peer_evidence"]) == 0
    assert any("n/a" in log.lower() for log in result["logs"])


def test_proxy_isolation_from_canonical_ratios_and_composite_m_score():
    """
    PROVENANCE & METHODOLOGICAL PURITY TEST:
    Verify that operational screening proxies (e.g. debtor days ratio, OPM margin ratio)
    can NEVER enter canonical financial ratios (DSRI, GMI) or the composite Beneish M-Score.
    """
    # 1. Analytics engine: with missing balance sheet items, canonical ratios remain None
    res = FinancialAnalytics.compute_beneish_sub_indices(
        sales_t=2000.0, sales_prev=1800.0,
        opm_t=20.0, opm_prev=25.0,              # Provides OPM proxy
        debtor_days_t=25.0, debtor_days_prev=20.0  # Provides Debtor Days proxy
    )

    # Canonical ratios must be None
    assert res.dsri is None
    assert res.gmi is None
    assert res.composite_m_score is None
    assert res.is_complete_m_score is False

    # Proxies are strictly segregated
    assert res.opm_margin_ratio_proxy == pytest.approx(25.0 / 20.0, rel=1e-3)
    assert res.debtor_days_ratio_proxy == pytest.approx(25.0 / 20.0, rel=1e-3)

    # 2. ForensicEngine audit_company: typical quarterly disclosures without balance sheet
    raw_data = {
        "ticker": "PROXYCO",
        "company_name": "Proxy Test Co",
        "quarters": {
            "periods": ["Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
            "rows": {
                "Sales": [1000.0, 1020.0, 1040.0, 1060.0, 1100.0],
                "Expenses": [800.0, 810.0, 820.0, 840.0, 880.0],
                "Operating Profit": [200.0, 210.0, 220.0, 220.0, 220.0],
                "OPM %": [20.0, 20.6, 21.2, 20.8, 20.0]
            }
        },
        "ratios_table": {
            "periods": ["Mar 2024", "Mar 2025"],
            "rows": {
                "Debtor Days": [15.0, 19.0]
            }
        },
        "balance_sheet": {"rows": {}},  # Empty balance sheet!
        "cash_flow": {"rows": {}}
    }

    summary = ForensicEngine.audit_company(raw_data)
    assert summary.beneish_components is not None
    assert summary.beneish_components.composite_m_score is None
    assert summary.beneish_components.is_complete_m_score is False
    assert len(summary.beneish_components.missing_components) > 0
    # No proxy was substituted into canonical ratio slots
    assert summary.beneish_dsri is None
    assert summary.beneish_gmi is None
    assert summary.debtor_days_ratio_proxy == pytest.approx(19.0 / 15.0, rel=1e-3)


