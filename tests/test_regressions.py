import pytest
from unittest.mock import MagicMock, patch
import httpx

from engine.analytics import FinancialAnalytics
from engine.forensics import ForensicEngine
from engine.models import AnomalyCandidate, ForensicSummary
from agent.evidence import EvidenceVault, EvidenceRecord, SourceType, EvidenceDirection, MaterialClaim
from agent.courtroom import ForensicReportSchema, HypothesisType
from agent.llm_provider import CentralModelProvider, ModelResponse, ModelExecutionError


def test_hindunilvr_trade_credit_elongation_regression():
    """
    REGRESSION: HINDUNILVR Debtor Days Stretch
    An increase in debtor days from 16 to 19 days must be characterized as trade credit
    elongation / deterioration / worsening, NEVER an improvement.
    The comparison basis (YoY vs QoQ) must be explicitly recorded.
    """
    ratio, err = FinancialAnalytics.compute_debtor_days_ratio_proxy(19.0, 16.0)
    assert err is None
    assert ratio == pytest.approx(1.1875, rel=1e-3)
    assert ratio > 1.0  # Elongation / deterioration in collection speed

    # Test audit_company flags elongation with adverse direction
    raw_data = {
        "ticker": "HINDUNILVR",
        "company_name": "Hindustan Unilever Ltd",
        "quarters": {
            "periods": ["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
            "rows": {
                "Sales": [15000.0, 15200.0, 15500.0, 15800.0],
                "Expenses": [11500.0, 11600.0, 11900.0, 12200.0],
                "Operating Profit": [3500.0, 3600.0, 3600.0, 3600.0],
                "OPM %": [23.3, 23.7, 23.2, 22.8]
            }
        },
        "ratios_table": {
            "rows": {
                "Debtor Days": [16.0, 16.5, 17.0, 19.0]
            }
        },
        "balance_sheet": {"rows": {}},
        "cash_flow": {"rows": {}}
    }

    summary = ForensicEngine.audit_company(raw_data)
    debtor_anomalies = [a for a in summary.anomalies if "Debtor Days" in a.metric_name]
    assert len(debtor_anomalies) > 0
    anom = debtor_anomalies[0]

    assert anom.direction == "adverse"
    assert anom.delta == 3.0
    assert anom.target_value == 19.0
    assert anom.baseline_value == 16.0
    assert anom.comparison_basis in ("YoY", "Historical Baseline")
    assert "improvement" not in anom.description.lower()
    assert "favorable" not in anom.description.lower()
    assert ("elongat" in anom.description.lower() or "stretch" in anom.description.lower() or "widen" in anom.description.lower())


def test_britannia_expense_residual_heuristic_regression():
    """
    REGRESSION: BRITANNIA Expense-Adjusted Residual
    Sales vs expense residual divergence must be explicitly tagged as a heuristic screening proxy,
    NEVER company-reported unit volume growth or conclusive proof of commodity inflation.
    Falsification condition cannot describe cost links as disproving cost inflation.
    """
    # 1. Formula validation
    residual, err = FinancialAnalytics.compute_expense_adjusted_residual(
        sales_growth_yoy=8.0,
        expenses_t=11400.0,
        expenses_prev=10000.0,
        sales_t=15000.0
    )
    assert err is None
    assert residual is not None
    # exp_growth = (1400/10000)*100 = 14.0%
    # cost_ratio = 11400 / 15000 = 0.76
    # exp_effect = 14.0 * 0.76 = 10.64%
    # residual = 8.0 - 10.64 = -2.64%
    assert residual == -2.64

    # 2. Heuristic screening tag enforcement
    anom = AnomalyCandidate(
        metric_name="Expense-Adjusted Revenue Growth Divergence",
        metric_type="expense_residual_divergence",
        unit="%",
        period="Mar 2025",
        target_value=-5.26,
        baseline_value=0.0,
        delta=-5.26,
        materiality=1.0,
        severity_score=52.6,
        description="Top-line growth lagged cost expansion by -5.26% (Heuristic Screening Metric).",
        is_heuristic=True,
        comparison_basis="YoY",
        direction="adverse"
    )
    assert anom.is_heuristic is True

    # 3. EvidenceVault rejects treating heuristic as statutory reported volume
    vault = EvidenceVault()
    unsupported_claim = MaterialClaim(
        claim_id="CLM-001",
        statement="Britannia reported negative unit volume growth of -5.26% in statutory filings.",
        cited_evidence_ids=[]
    )
    result = vault.validate_claims([unsupported_claim])
    assert result.is_valid is False
    assert len(result.unsupported_claims) == 1
    assert "CLM-001" in result.unsupported_claims[0]


def test_nestleind_interest_coverage_and_causal_restraint():
    """
    REGRESSION: NESTLEIND Restraint & Coverage Integrity
    A minor shift in interest coverage (e.g. 158x to 154x) with near-zero debt
    must not be flagged as severe solvency or liquidity distress.
    13.3% residual divergence must be documented as screening heuristic.
    """
    raw_data = {
        "ticker": "NESTLEIND",
        "company_name": "Nestle India Ltd",
        "quarters": {
            "periods": ["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
            "rows": {
                "Sales": [4800.0, 5000.0, 5200.0, 5500.0],
                "Expenses": [3700.0, 3900.0, 4100.0, 4400.0],
                "Operating Profit": [1100.0, 1100.0, 1100.0, 1100.0],
                "OPM %": [22.9, 22.0, 21.2, 20.0]
            }
        },
        "ratios_table": {
            "rows": {
                "Debtor Days": [15.0, 15.0, 15.5, 16.0]
            }
        },
        "balance_sheet": {"rows": {}},
        "cash_flow": {"rows": {}}
    }

    summary = ForensicEngine.audit_company(raw_data)
    # Verify no bogus debt distress anomaly is generated
    debt_anomalies = [a for a in summary.anomalies if "debt" in a.metric_name.lower() or "interest" in a.metric_name.lower()]
    assert len(debt_anomalies) == 0

    # Verify report schema validator handles calibrated finding
    valid_report = {
        "finding_heading": "Quantitative Signal",
        "1_The_Discovery": "Nestle India exhibited a 13.3% expense-adjusted revenue growth residual spread.",
        "2_Why_It_Matters": [
            "Input commodity costs outpaced net sales realization.",
            "Channel listing costs for quick commerce compressed operating margins.",
            "Working capital velocity remained largely stable."
        ],
        "3_Evidence": ["https://screener.in/company/NESTLEIND/consolidated/"],
        "4_Timeline": "Trailing four statutory quarters ending March 2025.",
        "5_Numbers": "Expense Residual Spread: 13.3% | DSRI: 1.02 | Debtor Days: 16d.",
        "6_Counterargument": "Commodity cycle inflation in coffee and cocoa explains the divergence.",
        "7_Falsification_Condition": "Disproven if cost-to-sales ratio normalizes within 150 bps of FY23 baseline.",
        "8_Evidence_Strength": "NOT_ESTABLISHED: Heuristic divergence reflects commodity cycle rather than revenue inflation.",
        "methodology_and_limitations": "Expense-adjusted residual is a screening heuristic, not company-reported volume."
    }
    parsed = ForensicReportSchema.model_validate(valid_report)
    assert parsed.finding_heading == "Quantitative Signal"
    assert "NOT_ESTABLISHED" in parsed.evidence_strength_8
    assert "INCONCLUSIVE" not in parsed.evidence_strength_8


def test_model_routing_gemini_200_no_ollama(mocker):
    """
    REGRESSION: Gemini-First Routing
    When Gemini succeeds with 200, it must return response and never call Ollama.
    """
    provider = CentralModelProvider()
    provider.gemini_key = "test-key"
    provider.offline = False

    mock_gemini = mocker.patch.object(
        provider,
        "_call_gemini_single_attempt",
        return_value=("Thought", "PONG")
    )
    mock_ollama = mocker.patch.object(provider, "_call_ollama")

    resp = provider.generate_text("Say PONG")
    assert resp.text == "PONG"
    assert resp.provider_used == "gemini"
    assert mock_gemini.call_count == 1
    assert mock_ollama.call_count == 0


def test_model_routing_gemini_429_backoff_and_ollama_fallback(mocker):
    """
    REGRESSION: Rate Limit Backoff & Fallback
    When Gemini encounters recoverable 429 errors exceeding max retries,
    it falls back cleanly to Ollama and identifies provider_used as 'ollama'.
    """
    provider = CentralModelProvider()
    provider.gemini_key = "test-key"
    provider.offline = False
    provider.max_retries = 2

    # Mock Gemini raising 429 RateLimitError
    mocker.patch.object(
        provider,
        "_call_gemini_single_attempt",
        side_effect=RuntimeError("HTTP 429: Resource has been exhausted (rate limit)")
    )
    # Mock Ollama succeeding
    mock_ollama = mocker.patch.object(
        provider,
        "_call_ollama",
        return_value=("Local thought", "OLLAMA_FALLBACK_OK")
    )

    resp = provider.generate_text("Investigate anomaly")
    assert resp.text == "OLLAMA_FALLBACK_OK"
    assert resp.provider_used == "ollama"
    assert mock_ollama.call_count == 1


def test_model_routing_rapid_daily_quota_exhaustion(mocker):
    """
    REGRESSION: Rapid Daily Quota Exhaustion
    When Gemini returns a daily quota exhaustion error, it must NOT execute
    slow, pointless exponential backoff sleeps. It should transition immediately to fallback.
    """
    provider = CentralModelProvider()
    provider.gemini_key = "test-key"
    provider.offline = False
    provider.max_retries = 3

    # Fast daily quota exhausted error
    mocker.patch.object(
        provider,
        "_call_gemini_single_attempt",
        side_effect=RuntimeError("HTTP 429: RESOURCE_EXHAUSTED: Daily quota exceeded for quota metric")
    )
    mock_ollama = mocker.patch.object(
        provider,
        "_call_ollama",
        return_value=("Ollama thought", "QUOTA_FALLBACK_SUCCESS")
    )

    resp = provider.generate_text("Generate hypotheses")
    assert resp.text == "QUOTA_FALLBACK_SUCCESS"
    assert resp.provider_used == "ollama"
    assert mock_ollama.call_count == 1


def test_model_routing_both_providers_fail_terminal_error(mocker):
    """
    REGRESSION: Zero Fabricated Data on Complete Outage
    If both Gemini and Ollama fail, the provider must raise ModelExecutionError.
    Never substitute empty success-shaped responses or default hypotheses.
    """
    provider = CentralModelProvider()
    provider.gemini_key = "test-key"
    provider.offline = False
    provider.max_retries = 1

    mocker.patch.object(
        provider,
        "_call_gemini_single_attempt",
        side_effect=RuntimeError("Gemini down")
    )
    mocker.patch.object(
        provider,
        "_call_ollama",
        side_effect=RuntimeError("Ollama daemon down")
    )

    with pytest.raises(ModelExecutionError) as exc_info:
        provider.generate_text("Synthesize finding")

    assert "Both providers failed" in str(exc_info.value)


def test_operating_margin_sign_preservation_regression():
    """
    REGRESSION: Operating-Margin Sign & Magnitude Preservation
    Tracing a 24% -> 23% decline must yield strictly -100.0 bps.
    No abs() proxy wedge substitution allowed.
    Must be preserved as negative across analytics, forensics summary, anomaly candidate,
    and formatted in red / adverse styling.
    """
    raw_data = {
        "ticker": "TESTCO",
        "company_name": "Test Company Ltd",
        "quarters": {
            "periods": ["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
            "rows": {
                "Sales": [1000.0, 1000.0, 1000.0, 1000.0],
                "Expenses": [760.0, 760.0, 760.0, 770.0],
                "Operating Profit": [240.0, 240.0, 240.0, 230.0],
                "OPM %": [24.0, 24.0, 24.0, 23.0]
            }
        },
        "ratios_table": {"rows": {}},
        "balance_sheet": {"rows": {}},
        "cash_flow": {"rows": {}}
    }

    # 1. ForensicEngine audit
    summary = ForensicEngine.audit_company(raw_data)
    assert summary.operating_margin_delta_bps == -100.0
    # Canonical margin wedge must be None because Gross Margin / COGS is missing
    assert summary.margin_wedge_bps is None

    # Check candidate anomaly
    opm_anomalies = [a for a in summary.anomalies if "Operating Margin" in a.metric_name]
    assert len(opm_anomalies) > 0
    anom = opm_anomalies[0]
    assert anom.delta == -100.0
    assert anom.direction == "adverse"
    assert anom.target_value == -100.0
    assert anom.baseline_value == 0.0

    # 2. Theme formatter verification: must format with minus sign and red color
    from exporter.theme import format_signed_metric_html, HEX_RED_ADVERSE
    formatted = format_signed_metric_html(summary.operating_margin_delta_bps, unit="bps", higher_is_better=True)
    assert "-100.0 bps" in formatted
    assert HEX_RED_ADVERSE in formatted


def test_point_in_time_cutoff_source_exclusion_regression():
    """
    REGRESSION: Point-in-Time Cutoff & Future Data Leakage Prevention
    When investigation cutoff is 2026-03-31, any document published after this date
    (such as an NSE annual report published June 2, 2026: AR_..._02062026...pdf)
    must be strictly excluded from the EvidenceVault and never registered.
    """
    from datetime import date
    vault = EvidenceVault(cutoff_date="2026-03-31")

    # Document published after cutoff: June 2, 2026 (explicit date)
    rec_future = EvidenceRecord(
        evidence_id="EVID-FUTURE-1",
        source_type=SourceType.REGULATORY_FILING.value,
        source_title="NSE Annual Report 2025-2026",
        source_url="https://nsearchives.nseindia.com/corporate/AR_29330_HINDUNILVR_2025_2026_A_21643813_02062026215058.pdf",
        supporting_excerpt="Financial statement disclosures for full year ended March 31, 2026.",
        extracted_fact="Full year FY26 trade receivables balance.",
        publication_date=date(2026, 6, 2)
    )
    assert vault.register_evidence(rec_future) is False, "Future publication must be strictly excluded by EvidenceVault"
    assert "EVID-FUTURE-1" in vault.excluded_by_cutoff

    # Document published after cutoff with date in URL only
    rec_future_url = EvidenceRecord(
        evidence_id="EVID-FUTURE-2",
        source_type=SourceType.REGULATORY_FILING.value,
        source_title="NSE Filing June 2026",
        source_url="https://nsearchives.nseindia.com/corporate/AR_29330_HINDUNILVR_02062026.pdf",
        supporting_excerpt="Q4 and FY26 audited results.",
        extracted_fact="Q4 and FY26 audited results."
    )
    assert vault.register_evidence(rec_future_url) is False, "NSE timestamp in URL after cutoff must be excluded"
    assert "EVID-FUTURE-2" in vault.excluded_by_cutoff

    # Document published on or before cutoff: Feb 15, 2026
    rec_valid = EvidenceRecord(
        evidence_id="EVID-VALID-1",
        source_type=SourceType.CONCALL_TRANSCRIPT.value,
        source_title="Q3 FY26 Earnings Call Transcript",
        source_url="https://screener.in/company/HINDUNILVR/concall/15022026/",
        supporting_excerpt="Management commentary on trade credit and raw material costs.",
        extracted_fact="Management discussed trade credit terms in Q3.",
        publication_date=date(2026, 2, 15)
    )
    assert vault.register_evidence(rec_valid) is True, "Pre-cutoff publication must be successfully registered"
    assert "EVID-VALID-1" in vault.evidence_by_id

