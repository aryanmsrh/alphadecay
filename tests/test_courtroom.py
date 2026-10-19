import pytest
from unittest.mock import MagicMock
from pydantic import ValidationError
from agent.courtroom import (
    ForensicReportSchema, AdjudicationVerdict, DataSufficiency,
    AdjudicationResult, migrate_legacy_verdict
)
from agent.nodes import reflection_router, adversarial_critic_node

def test_forensic_report_schema_validation():
    data = {
        "finding_heading": "Observed Fact (Causal Explanation Not Established)",
        "1_The_Discovery": "HUL expanded debtor days from 16d to 19d amid channel credit elongation, but causal mechanism remains unproven.",
        "2_Why_It_Matters": [
            "Trade credit terms relaxed across traditional channels.",
            "Working capital intensity increased relative to operating profit.",
            "Peer spread widened by 1.5d vs sector median."
        ],
        "3_Evidence": ["https://screener.in/company/HINDUNILVR/", "https://bseindia.com/filing.pdf"],
        "4_Timeline": "Trailing 8 statutory quarters ending Jun 2026.",
        "5_Numbers": "Canonical DSRI: 1.188 | Debtor Days: +3.0d | Margin Wedge: 0.0 bps.",
        "6_Counterargument": "Festive inventory stocking and seasonal channel credit normalization.",
        "7_Falsification_Condition": "Disproven if debtor days compress below 16d for >=2 consecutive quarters.",
        "8_Evidence_Strength": "NOT_ESTABLISHED (Data Sufficiency: LIMITED): Evidence permits both seasonal channel push and macro slowdown."
    }
    report = ForensicReportSchema.model_validate(data)
    assert report.discovery_1.startswith("HUL expanded")
    assert len(report.why_it_matters_2) == 3
    assert len(report.evidence_3) == 2
    assert "NOT_ESTABLISHED" in report.evidence_strength_8
    assert "INCONCLUSIVE" not in report.evidence_strength_8

def test_forensic_report_schema_strictly_rejects_inconclusive():
    """
    EPISTEMOLOGICAL INVARIANT:
    The obsolete verdict 'INCONCLUSIVE' must be strictly rejected by ForensicReportSchema.
    """
    invalid_data = {
        "finding_heading": "Investigative Lead",
        "1_The_Discovery": "HUL debtor days widened with an inconclusive result.",
        "2_Why_It_Matters": ["Point 1", "Point 2", "Point 3"],
        "3_Evidence": ["https://screener.in/company/HINDUNILVR/"],
        "4_Timeline": "Trailing quarters",
        "5_Numbers": "Delta = +3d",
        "6_Counterargument": "Seasonal",
        "7_Falsification_Condition": "Normalization",
        "8_Evidence_Strength": "INCONCLUSIVE: Data is conflicting."
    }
    with pytest.raises(ValidationError) as exc:
        ForensicReportSchema.model_validate(invalid_data)
    assert "INCONCLUSIVE" in str(exc.value)

    # Also rejected in discovery_1
    invalid_discovery = dict(invalid_data)
    invalid_discovery["8_Evidence_Strength"] = "NOT_ESTABLISHED: Incomplete disclosures."
    invalid_discovery["1_The_Discovery"] = "Findings are inconclusive."
    with pytest.raises(ValidationError) as exc2:
        ForensicReportSchema.model_validate(invalid_discovery)
    assert "INCONCLUSIVE" in str(exc2.value)

def test_legacy_verdict_migration():
    assert migrate_legacy_verdict("INCONCLUSIVE") == "NOT_ESTABLISHED"
    assert migrate_legacy_verdict("INSUFFICIENT_DATA") == "NOT_ESTABLISHED"
    assert migrate_legacy_verdict("FALSIFIED") == "REFUTED"
    assert migrate_legacy_verdict("SUPPORTED") == "SUPPORTED"
    assert migrate_legacy_verdict("REFUTED") == "REFUTED"
    assert migrate_legacy_verdict("NOT_ESTABLISHED") == "NOT_ESTABLISHED"

def test_reflection_router_loops_back_on_refuted():
    # State where hypothesis was refuted and more anomalies remain
    state = {
        "is_falsified": True,
        "current_anomaly_index": 1,
        "anomalies": [{"metric_name": "A1"}, {"metric_name": "A2"}, {"metric_name": "A3"}]
    }
    route = reflection_router(state)
    assert route == "loop_back"

def test_reflection_router_proceeds_when_all_evaluated():
    # State where all anomalies have been evaluated
    state = {
        "is_falsified": True,
        "current_anomaly_index": 3,
        "anomalies": [{"metric_name": "A1"}, {"metric_name": "A2"}, {"metric_name": "A3"}]
    }
    route = reflection_router(state)
    assert route == "proceed"

def test_reflection_router_proceeds_on_supported_or_not_established():
    state_supported = {
        "is_falsified": False,
        "adjudication_verdict": "SUPPORTED",
        "current_anomaly_index": 0,
        "anomalies": [{"metric_name": "A1"}]
    }
    assert reflection_router(state_supported) == "proceed"

    state_not_established = {
        "is_falsified": False,
        "adjudication_verdict": "NOT_ESTABLISHED",
        "current_anomaly_index": 0,
        "anomalies": [{"metric_name": "A1"}]
    }
    assert reflection_router(state_not_established) == "proceed"

def test_adversarial_critic_node_adjudicates_calibrated_verdicts(mocker):
    # Mock central provider to return a NOT_ESTABLISHED verdict
    mock_resp = MagicMock()
    mock_resp.provider_used = "gemini"
    mock_resp.model_name = "gemini-3.5-flash-lite"
    mock_resp.text = """
    {
      "prosecution_case": "Receivables grew faster than sales.",
      "defense_case": "Macro supply chain adjustments explain the shift.",
      "verdict": "NOT_ESTABLISHED",
      "data_sufficiency": "LIMITED",
      "evidence_strength": "Moderate",
      "adjudication_rationale": "Data is insufficient to rule out festive seasonality.",
      "falsification_condition": "Disproven if debtor days normalize below 15d.",
      "next_investigation_step": "Obtain channel aging schedule from next audited release."
    }
    """
    mocker.patch("agent.nodes.central_provider.generate_text", return_value=mock_resp)

    state = {
        "ticker": "TEST",
        "company_name": "Test Co",
        "selected_anomaly": {"metric_name": "Debtor Days", "period": "Q4", "delta": 3.0},
        "adverse_hypothesis": "Channel stuffing",
        "benign_hypothesis": "Festive timing",
        "computed_metrics": {},
        "prosecution_evidence": [],
        "peer_evidence": []
    }

    result = adversarial_critic_node(state)
    assert result["is_falsified"] is False
    assert result["adjudication"]["verdict"] == "NOT_ESTABLISHED"
    assert result["adjudication"]["data_sufficiency"] == "LIMITED"
    assert "festive seasonality" in result["adjudication"]["rationale"]
    assert "INCONCLUSIVE" not in result["adjudication"]["verdict"]
