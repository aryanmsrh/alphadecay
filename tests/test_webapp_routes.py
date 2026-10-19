"""
Unit & Route Tests for ALPHA-DECAY Flask Web Application.
Tests HTTP routes, API endpoints, parameter validation, error responses, and pagination.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timezone
from webapp.app import create_app
from webapp.run_store import RunStore


@pytest.fixture
def app(tmp_path, mocker):
    test_db = tmp_path / "test_alphadecay.db"
    store = RunStore(db_path=test_db)
    mocker.patch("webapp.app.run_store", store)
    mocker.patch("webapp.services.run_store", store)

    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "ENFORCE_CSRF": False
    })
    app.test_store = store
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def test_dashboard_loads(client):
    """Verify main dashboard landing page loads with 200 OK and expected structure."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "ALPHA-DECAY" in html
    assert "FINANCIAL INTELLIGENCE" in html
    assert "Total Completed" in html
    assert "Active Investigations" in html


def test_new_investigation_page_loads(client):
    """Verify investigation creation page renders form and preset tickers."""
    resp = client.get("/investigations/new")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Launch Autonomous Forensic Investigation" in html
    assert "HINDUNILVR" in html
    assert "ITC" in html
    assert "NESTLEIND" in html


def test_investigation_form_validation(client):
    """Verify validation for empty/invalid tickers and malformed cutoff dates."""
    # Empty ticker
    resp = client.post("/api/investigations", json={"ticker": ""})
    assert resp.status_code == 400
    assert "Invalid ticker symbol" in resp.get_json()["error"]

    # Malformed ticker
    resp = client.post("/api/investigations", json={"ticker": "INVALID!@#$%"})
    assert resp.status_code == 400
    assert "invalid characters" in resp.get_json()["error"]

    # Malformed cutoff date
    resp = client.post("/api/investigations", json={"ticker": "ITC", "cutoff_date": "not-a-date"})
    assert resp.status_code == 400
    assert "Invalid cutoff date" in resp.get_json()["error"]


def test_valid_submission_creates_persisted_run(client, mocker):
    """Verify that submitting a valid investigation persists a QUEUED record and queues background work."""
    # Prevent background thread from calling real external APIs
    mock_executor = mocker.patch("webapp.services.investigation_service.executor.submit")

    resp = client.post(
        "/api/investigations",
        json={"ticker": "HINDUNILVR", "cutoff_date": "2024-12-31", "max_anomalies": 2}
    )
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["success"] is True
    assert "run_id" in data
    assert data["status"] == "QUEUED"
    assert "/investigations/" in data["redirect_url"]

    # Verify run exists in store
    run_id = data["run_id"]
    saved_run = client.application.test_store.get_run(run_id)
    assert saved_run is not None
    assert saved_run["ticker"] == "HINDUNILVR"
    assert saved_run["cutoff_date"] == "2024-12-31"
    assert saved_run["status"] == "QUEUED"
    assert mock_executor.called


def test_unknown_run_id_returns_404(client):
    """Verify 404 response for nonexistent run IDs across page and API endpoints."""
    # Page
    resp = client.get("/investigations/RUN-NONEXISTENT-999")
    assert resp.status_code == 404

    # API
    resp = client.get("/api/investigations/RUN-NONEXISTENT-999")
    assert resp.status_code == 404
    assert "not found" in resp.get_json()["error"]


def test_progress_events_retrieval(client):
    """Verify that stage events can be queried via API."""
    store = client.application.test_store
    run_id = "RUN-EVENT-TEST-1"
    store.create_run(run_id=run_id, ticker="ITC")
    store.add_event(run_id=run_id, stage="data_ingestion", message="Scraping disclosures", severity="INFO")
    store.add_event(run_id=run_id, stage="financial_analytics", message="Math sandbox complete", severity="SUCCESS")

    resp = client.get(f"/api/investigations/{run_id}/events")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["run_id"] == run_id
    assert len(payload["events"]) >= 2
    assert payload["events"][-1]["stage"] == "financial_analytics"


def test_history_filters_and_pagination(client):
    """Verify list filtering and pagination mechanics."""
    store = client.application.test_store
    for i in range(15):
        ticker = "HINDUNILVR" if i % 2 == 0 else "ITC"
        status = "SUCCEEDED" if i < 10 else "FAILED"
        r_id = f"RUN-HIST-{i}"
        store.create_run(run_id=r_id, ticker=ticker)
        store.update_run_status(run_id=r_id, status=status)

    # Test pagination (per_page=5)
    resp = client.get("/api/investigations?page=1&per_page=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["runs"]) == 5
    assert data["total"] == 15
    assert data["total_pages"] == 3

    # Test ticker filter
    resp = client.get("/api/investigations?ticker=ITC")
    assert resp.status_code == 200
    data = resp.get_json()
    for r in data["runs"]:
        assert r["ticker"] == "ITC"

    # Test status filter
    resp = client.get("/api/investigations?status=FAILED")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 5
    for r in data["runs"]:
        assert r["status"] == "FAILED"


def test_diagnostics_and_health_endpoints(client):
    """Verify health and diagnostics endpoints return expected JSON shapes without leaking secrets."""
    # Health endpoint
    h_resp = client.get("/api/health")
    assert h_resp.status_code == 200
    h_data = h_resp.get_json()
    assert h_data["status"] == "HEALTHY"
    assert "gemini_model" in h_data
    assert "AIza" not in str(h_data)  # Ensure no key leak

    # Diagnostics endpoint
    d_resp = client.get("/api/diagnostics")
    assert d_resp.status_code == 200
    d_data = d_resp.get_json()
    assert "gemini_model_configured" in d_data
    assert "ollama_fallback_model" in d_data
    assert "gemini_key_present" in d_data
    assert "AIza" not in str(d_data)
