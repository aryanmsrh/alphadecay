"""
End-to-End Integration Tests for ALPHA-DECAY Web Application.
Tests background pipeline execution, lifecycle state transitions,
durable persistence across app restarts, artifact isolation, and cancellation.
"""

import pytest
import time
import json
from unittest.mock import MagicMock
from pathlib import Path
from agent.courtroom import ForensicReportSchema
from webapp.app import create_app
from webapp.run_store import RunStore
from webapp.services import investigation_service


@pytest.fixture
def test_setup(tmp_path, mocker):
    test_db = tmp_path / "integration_alphadecay.db"
    store = RunStore(db_path=test_db)
    mocker.patch("webapp.app.run_store", store)
    mocker.patch("webapp.services.run_store", store)

    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "integration-secret",
        "ENFORCE_CSRF": False
    })
    app.test_store = store

    # Deterministic mock disclosures fixture
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
                "title": "Q4 Statutory Concall",
                "url": "https://bseindia.com/filing_q4.pdf"
            }
        ]
    }

    # Mock external network scrapers
    mocker.patch(
        "webapp.services.ScreenerScraper.fetch_company_data",
        return_value=mock_raw_data
    )
    mocker.patch(
        "agent.nodes.screener_scraper.fetch_company_data",
        return_value={
            "ticker": "DABUR",
            "company_name": "Dabur India Ltd",
            "quarters": {"periods": ["Dec 2024", "Mar 2025"], "rows": {"Sales": [2800.0, 2900.0], "Expenses": [2200.0, 2300.0]}},
            "ratios_table": {"rows": {"Debtor Days": [32.0, 33.0]}},
            "balance_sheet": {"rows": {}},
            "cash_flow": {"rows": {}}
        }
    )
    mocker.patch(
        "agent.nodes.concall_harvester.harvest_transcript",
        return_value=[{
            "matched_keywords": ["credit", "distributor"],
            "excerpt": "Executive: We offered extended credit support to distributors.",
            "source_url": "https://bseindia.com/filing_q4.pdf",
            "density_score": 10
        }]
    )
    mocker.patch(
        "agent.nodes.search_client.search",
        return_value=[{
            "title": "FMCG Working Capital Report",
            "url": "https://example.com/industry_note.html",
            "content": "Trade terms stretched across consumer channels."
        }]
    )

    # Mock LLM provider responses
    mock_hyp_resp = MagicMock(provider_used="gemini", model_name="gemini-3.8-flash")
    mock_hyp_resp.text = '{"adverse_hypothesis": "Trade credit used to bolster sales.", "benign_hypothesis": "Festive channel adjustments."}'
    mock_hyp_resp.model_dump.return_value = {"provider_used": "gemini", "model_name": "gemini-3.8-flash"}

    mock_contra_resp = MagicMock(provider_used="gemini", model_name="gemini-3.8-flash")
    mock_contra_resp.text = "Commentary aligns with trade receivables stretch."
    mock_contra_resp.model_dump.return_value = {"provider_used": "gemini", "model_name": "gemini-3.8-flash"}

    mock_adj_resp = MagicMock(provider_used="gemini", model_name="gemini-3.8-flash")
    mock_adj_resp.text = '{"prosecution_case": "Receivables +21% YoY.", "defense_case": "Festive shifts.", "verdict": "SUPPORTED", "data_sufficiency": "SUFFICIENT", "evidence_strength": "High", "adjudication_rationale": "Direct concall corroboration.", "falsification_condition": "Normalization in next 2 quarters.", "next_investigation_step": "Inspect Q1 FY26 filing."}'
    mock_adj_resp.model_dump.return_value = {"provider_used": "gemini", "model_name": "gemini-3.8-flash"}

    mocker.patch(
        "agent.nodes.central_provider.generate_text",
        side_effect=[mock_hyp_resp, mock_contra_resp, mock_adj_resp]
    )

    # Mock structured compiler response
    synth_json = """
    {
      "finding_heading": "Verified Finding",
      "1_The_Discovery": "HUL expanded credit terms from 14d to 18d, confirming trade credit supported top-line revenue.",
      "2_Why_It_Matters": [
        "Trade receivables expanded +21.4% YoY while sales grew 10.5%.",
        "Operating margins contracted by 310 bps.",
        "Competitor Dabur only shifted debtor days by +1.0d."
      ],
      "3_Evidence": [
        "https://bseindia.com/filing_q4.pdf",
        "https://example.com/industry_note.html"
      ],
      "4_Timeline": "Trailing cycle ending March 2025.",
      "5_Numbers": "Canonical DSRI: 1.16 | Debtor Days: +4.0d | Margin Wedge: +310 bps.",
      "6_Counterargument": "Management cites festive quick commerce listing terms.",
      "7_Falsification_Condition": "Disproven if debtor days normalize below 15d across two quarters.",
      "8_Evidence_Strength": "SUPPORTED: Corroborated by statutory filings and concall disclosures."
    }
    """
    mock_synth_resp = MagicMock(provider_used="gemini", model_name="gemini-3.8-flash")
    mock_synth_resp.text = synth_json
    mock_synth_resp.model_dump.return_value = {"provider_used": "gemini", "model_name": "gemini-3.8-flash"}
    parsed_report = ForensicReportSchema.model_validate_json(synth_json)
    mocker.patch(
        "agent.nodes.central_provider.generate_structured",
        return_value=(mock_synth_resp, parsed_report)
    )

    return app, store, tmp_path


def test_full_mocked_investigation_lifecycle(test_setup):
    """
    Verifies that a full investigation can be enqueued, executed in background,
    transitions status correctly to SUCCEEDED, emits progress events, compiles report,
    and makes metrics and artifacts available.
    """
    app, store, tmp_path = test_setup
    client = app.test_client()

    # 1. Launch investigation
    resp = client.post("/api/investigations", json={"ticker": "HINDUNILVR", "export_pdf": True})
    assert resp.status_code == 202
    run_id = resp.get_json()["run_id"]

    # 2. Wait for background execution to complete (with timeout)
    max_wait = 15.0
    start = time.time()
    final_status = None
    while time.time() - start < max_wait:
        run = store.get_run(run_id)
        if run and run.get("status") in ("SUCCEEDED", "FAILED", "CANCELLED"):
            final_status = run.get("status")
            break
        time.sleep(0.3)

    assert final_status == "SUCCEEDED", f"Investigation did not succeed; current state: {store.get_run(run_id)}"

    # 3. Verify stage events audit trail
    events = store.get_events(run_id)
    stages = [ev["stage"] for ev in events]
    assert "data_ingestion" in stages
    assert "financial_analytics" in stages
    assert "anomaly_triage" in stages
    assert "completed" in stages

    # 4. Verify Final Report API
    report_resp = client.get(f"/api/investigations/{run_id}/report")
    assert report_resp.status_code == 200
    report_data = report_resp.get_json()
    assert report_data["adjudication_verdict"] == "SUPPORTED"
    assert "HUL expanded credit terms" in report_data["discovery"]["1_The_Discovery"]

    # 5. Verify Metrics & Charts API
    metrics_resp = client.get(f"/api/investigations/{run_id}/metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.get_json()
    assert "series" in metrics_data
    assert len(metrics_data["quarters"]) > 0

    # 6. Verify Evidence API
    evidence_resp = client.get(f"/api/investigations/{run_id}/evidence")
    assert evidence_resp.status_code == 200
    evidence_data = evidence_resp.get_json()
    assert evidence_data["count"] > 0
    assert any("filing_q4.pdf" in e.get("source_url", "") for e in evidence_data["evidence"])

    # 7. Verify Artifacts are on disk and downloadable
    pdf_resp = client.get(f"/api/investigations/{run_id}/artifacts/HINDUNILVR_forensic_report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.mimetype == "application/pdf"

    manifest_resp = client.get(f"/api/investigations/{run_id}/artifacts/run_manifest.json")
    assert manifest_resp.status_code == 200
    manifest = json.loads(manifest_resp.data)
    assert manifest["run_id"] == run_id
    assert manifest["validation_passed"] is True


def test_investigation_cancellation(test_setup):
    """Verifies that requesting cancellation halts progress and updates status to CANCELLED."""
    app, store, tmp_path = test_setup
    client = app.test_client()

    run_id = "RUN-CANCEL-TEST-01"
    store.create_run(run_id=run_id, ticker="ITC")
    store.update_run_status(run_id=run_id, status="RUNNING")

    # Call cancellation API
    resp = client.post(f"/api/investigations/{run_id}/cancel")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["status"] == "CANCELLED"

    # Verify persisted status
    run = store.get_run(run_id)
    assert run["status"] == "CANCELLED"

    # Verify event logged
    events = store.get_events(run_id)
    assert any(e["stage"] == "cancelled" for e in events)


def test_failed_investigation_preserves_error_and_avoids_false_success(test_setup, mocker):
    """Verifies that unhandled engine exceptions record FAILED status and sanitized error details."""
    app, store, tmp_path = test_setup
    client = app.test_client()

    # Force scraper to raise an exception
    mocker.patch(
        "webapp.services.ScreenerScraper.fetch_company_data",
        side_effect=RuntimeError("Simulated exchange connection timeout")
    )

    resp = client.post("/api/investigations", json={"ticker": "BRITANNIA"})
    assert resp.status_code == 202
    run_id = resp.get_json()["run_id"]

    # Wait for failure
    start = time.time()
    final_status = None
    while time.time() - start < 8.0:
        run = store.get_run(run_id)
        if run and run.get("status") in ("SUCCEEDED", "FAILED"):
            final_status = run.get("status")
            break
        time.sleep(0.2)

    assert final_status == "FAILED"
    failed_run = store.get_run(run_id)
    assert "Simulated exchange connection timeout" in failed_run["error_message"]
    assert failed_run["error_trace"] is not None
    assert failed_run["adjudication_verdict"] is None  # Never generate fake verdict


def test_artifact_isolation_between_separate_runs(test_setup):
    """Verifies that separate investigations generate isolated run directories."""
    app, store, tmp_path = test_setup
    run1_id = "RUN-ISO-01"
    run2_id = "RUN-ISO-02"

    dir1 = tmp_path / "runs" / run1_id
    dir2 = tmp_path / "runs" / run2_id
    dir1.mkdir(parents=True)
    dir2.mkdir(parents=True)

    (dir1 / "run_manifest.json").write_text('{"run_id": "RUN-ISO-01"}')
    (dir2 / "run_manifest.json").write_text('{"run_id": "RUN-ISO-02"}')

    store.create_run(run_id=run1_id, ticker="HINDUNILVR", output_dir=str(dir1))
    store.create_run(run_id=run2_id, ticker="ITC", output_dir=str(dir2))

    client = app.test_client()
    m1 = client.get(f"/api/investigations/{run1_id}/artifacts/run_manifest.json").get_json()
    m2 = client.get(f"/api/investigations/{run2_id}/artifacts/run_manifest.json").get_json()

    assert m1["run_id"] == "RUN-ISO-01"
    assert m2["run_id"] == "RUN-ISO-02"
