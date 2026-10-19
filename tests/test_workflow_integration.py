import pytest
from unittest.mock import MagicMock
from pathlib import Path
import pypdf

from agent.graph import build_investigation_graph
from engine.forensics import ForensicEngine
from exporter.pdf_report import export_forensic_pdf

def test_full_investigation_workflow_end_to_end(mocker, tmp_path):
    """
    INTEGRATION TEST:
    Executes the complete LangGraph workflow from raw financials to 8-point schema
    and PDF generation using deterministic fixtures and mocked external APIs.
    """
    # 1. Deterministic Financial Data Fixture
    mock_raw_data = {
        "ticker": "HINDUNILVR",
        "company_name": "Hindustan Unilever Ltd",
        "quarters": {
            "periods": ["Dec 2023", "Mar 2024", "Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025"],
            "rows": {
                "Sales": [15000.0, 15200.0, 15500.0, 15800.0, 16200.0, 16800.0],
                "Expenses": [11500.0, 11600.0, 12000.0, 12200.0, 12800.0, 13400.0],
                "Operating Profit": [3500.0, 3600.0, 3500.0, 3600.0, 3400.0, 3400.0],
                "OPM %": [23.3, 23.7, 22.6, 22.8, 21.0, 20.2]
            }
        },
        "balance_sheet": {
            "rows": {
                "Trade Receivables": [2800.0, 3400.0],
                "Other Assets": [1500.0, 1600.0],
                "Total Assets": [70000.0, 72000.0]
            }
        },
        "ratios_table": {
            "rows": {
                "Debtor Days": [14.0, 18.0]
            }
        },
        "cash_flow": {
            "rows": {
                "Cash from Operating Activity": [8500.0]
            }
        },
        "concall_transcripts": [
            {
                "title": "Q4 Earnings Concall",
                "url": "https://bseindia.com/filing_q4.pdf"
            }
        ]
    }

    # Deterministic Math Sandbox Execution
    summary = ForensicEngine.audit_company(mock_raw_data)
    assert len(summary.anomalies) > 0
    assert summary.beneish_dsri is not None

    # Mock external calls in nodes: Concall Harvester and Tavily Web Search
    mocker.patch(
        "agent.nodes.concall_harvester.harvest_transcript",
        return_value=[{
            "matched_keywords": ["credit", "distributor"],
            "excerpt": "Analyst: Can you speak about distributor credit? Management: We provided temporary credit support.",
            "source_url": "https://bseindia.com/filing_q4.pdf",
            "density_score": 10
        }]
    )
    mocker.patch(
        "agent.nodes.search_client.search",
        return_value=[{
            "title": "FMCG Distributor Credit Report",
            "url": "https://example.com/industry_note.html",
            "content": "FMCG firms extended credit terms to protect market share."
        }]
    )
    # Mock peer fetcher
    mocker.patch(
        "agent.nodes.screener_scraper.fetch_company_data",
        return_value={
            "ticker": "DABUR",
            "company_name": "Dabur India Ltd",
            "quarters": {"periods": ["Dec 2024", "Mar 2025"], "rows": {"Sales": [2800.0, 2900.0], "Expenses": [2200.0, 2300.0], "OPM %": [21.4, 20.7]}},
            "ratios_table": {"rows": {"Debtor Days": [32.0, 33.0]}},
            "balance_sheet": {"rows": {}},
            "cash_flow": {"rows": {}}
        }
    )

    # Mock central provider responses for the nodes
    mock_hypothesis_resp = MagicMock()
    mock_hypothesis_resp.provider_used = "gemini"
    mock_hypothesis_resp.model_name = "gemini-3.8-flash"
    mock_hypothesis_resp.text = """
    {
      "adverse_hypothesis": "Company used trade credit extensions to support headline volume.",
      "benign_hypothesis": "Festive timing and quick commerce channel shifts temporarily stretched DSO.",
      "discriminating_prediction": "Overdue aging schedules vs prompt dealer repayments.",
      "falsification_condition": "Disproven if debtor days compress below 15d in next 2 quarters."
    }
    """

    mock_contradiction_resp = MagicMock()
    mock_contradiction_resp.provider_used = "gemini"
    mock_contradiction_resp.model_name = "gemini-3.8-flash"
    mock_contradiction_resp.text = "Management admitted temporary credit support while claiming healthy cash flow."

    mock_adjudication_resp = MagicMock()
    mock_adjudication_resp.provider_used = "gemini"
    mock_adjudication_resp.model_name = "gemini-3.8-flash"
    mock_adjudication_resp.text = """
    {
      "prosecution_case": "Receivables increased 21% while sales only grew 10%.",
      "defense_case": "Macro quick commerce listing terms necessitated channel flexibility.",
      "verdict": "SUPPORTED",
      "evidence_strength": "Strong",
      "adjudication_rationale": "Direct concall confirmation of credit support aligns with canonical DSRI stretch.",
      "falsification_condition": "Debtor days normalizing below 15d across two quarters."
    }
    """

    mock_synthesis_resp = MagicMock()
    mock_synthesis_resp.provider_used = "gemini"
    mock_synthesis_resp.model_name = "gemini-3.8-flash"
    mock_synthesis_resp.text = """
    {
      "1_The_Discovery": "HUL expanded credit terms from 14d to 18d, confirming trade credit supported top-line revenue.",
      "2_Why_It_Matters": [
        "Trade receivables expanded +21.4% YoY while top-line grew 10.5%.",
        "Operating margins contracted by 350 bps under distribution expense pressure.",
        "Competitor Dabur only shifted debtor days by +1.0d."
      ],
      "3_Evidence": [
        "https://bseindia.com/filing_q4.pdf",
        "https://example.com/industry_note.html"
      ],
      "4_Timeline": "Trailing reporting cycle ending March 2025.",
      "5_Numbers": "Canonical DSRI: 1.16 | Debtor Days: +4.0d | Margin Wedge: +350 bps | Peer Spread: +3.0d.",
      "6_Counterargument": "Management cites quick commerce listing allowances and retail channel support.",
      "7_Falsification_Condition": "Disproven if debtor days normalize below 15d for two consecutive quarters.",
      "8_Evidence_Strength": "SUPPORTED: Confirmed by concall transcript and balance sheet trade receivables expansion."
    }
    """

    mocker.patch(
        "agent.nodes.central_provider.generate_text",
        side_effect=[
            mock_hypothesis_resp,
            mock_contradiction_resp,
            mock_adjudication_resp
        ]
    )

    from agent.courtroom import ForensicReportSchema
    parsed_report = ForensicReportSchema.model_validate_json(mock_synthesis_resp.text)
    mocker.patch(
        "agent.nodes.central_provider.generate_structured",
        return_value=(mock_synthesis_resp, parsed_report)
    )

    # 3. Compile and invoke LangGraph state machine
    app = build_investigation_graph()
    initial_state = {
        "run_id": "test_run_123",
        "ticker": "HINDUNILVR",
        "company_name": "Hindustan Unilever Ltd",
        "raw_financials": mock_raw_data,
        "computed_metrics": {
            "debtor_days": summary.debtor_days,
            "sales_growth_yoy": summary.sales_growth_yoy,
            "expense_adjusted_residual": summary.expense_adjusted_residual,
            "beneish_dsri": summary.beneish_dsri,
            "beneish_sgi": summary.beneish_sgi,
            "beneish_gmi": summary.beneish_gmi,
            "cfo_to_ebitda": summary.cfo_to_ebitda,
            "margin_wedge_bps": summary.margin_wedge_bps,
            "distribution_drag_bps": summary.distribution_drag_bps,
            "peer_spread_days": summary.peer_spread_days
        },
        "anomalies": [a.model_dump() for a in summary.anomalies],
        "selected_anomaly": None,
        "competing_hypotheses": [],
        "adverse_hypothesis": None,
        "benign_hypothesis": None,
        "prosecution_evidence": [],
        "peer_evidence": [],
        "contradiction_analysis": None,
        "adversarial_arguments": None,
        "adjudication": None,
        "is_falsified": False,
        "falsification_reason": None,
        "evidence_strength": None,
        "iteration_count": 0,
        "current_anomaly_index": 0,
        "final_discovery": None,
        "provider_metadata": {},
        "validation_passed": False,
        "logs": []
    }

    final_state = app.invoke(initial_state)

    # 4. Verify Final State
    assert final_state["validation_passed"] is True
    assert final_state["final_discovery"] is not None
    discovery = final_state["final_discovery"]
    assert "1_The_Discovery" in discovery
    assert "8_Evidence_Strength" in discovery
    assert discovery["8_Evidence_Strength"].startswith("SUPPORTED")
    assert len(discovery["3_Evidence"]) == 2

    # 5. Verify PDF Report Export from Final State
    pdf_path = str(tmp_path / "end_to_end_report.pdf")
    generated_pdf = export_forensic_pdf(
        ticker="HINDUNILVR",
        company_name="Hindustan Unilever Ltd",
        summary_data=summary,
        discovery=discovery,
        output_path=pdf_path
    )
    assert Path(generated_pdf).exists()
    reader = pypdf.PdfReader(generated_pdf)
    assert len(reader.pages) == 2
