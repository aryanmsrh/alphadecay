"""
Security Tests for ALPHA-DECAY Web Application.
Tests path traversal prevention, CSRF protection, HTML escaping/XSS prevention,
and credential sanitization.
"""

import pytest
import os
from pathlib import Path
from webapp.app import create_app
from webapp.run_store import RunStore


@pytest.fixture
def sec_app(tmp_path, mocker):
    test_db = tmp_path / "sec_alphadecay.db"
    store = RunStore(db_path=test_db)
    mocker.patch("webapp.app.run_store", store)
    mocker.patch("webapp.services.run_store", store)

    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "security-test-key",
        "ENFORCE_CSRF": True  # Explicitly enforce CSRF for security tests
    })
    app.test_store = store
    return app


def test_csrf_protection_on_state_changing_requests(sec_app):
    """Verify that state-changing requests without valid CSRF token are blocked with 403."""
    client = sec_app.test_client()

    # 1. POST without CSRF token
    resp = client.post("/api/investigations", json={"ticker": "HINDUNILVR"})
    assert resp.status_code == 403
    assert "CSRF" in resp.get_json()["error"]

    # 2. Get valid session and CSRF token
    get_resp = client.get("/investigations/new")
    assert get_resp.status_code == 200

    # Retrieve csrf_token from cookie/session
    with client.session_transaction() as sess:
        valid_csrf = sess.get("csrf_token")
    assert valid_csrf is not None

    # 3. POST with invalid CSRF token
    resp_bad = client.post(
        "/api/investigations",
        json={"ticker": "HINDUNILVR"},
        headers={"X-CSRF-Token": "invalid-token-1234"}
    )
    assert resp_bad.status_code == 403

    # 4. POST with valid CSRF token in header
    resp_good = client.post(
        "/api/investigations",
        json={"ticker": "HINDUNILVR"},
        headers={"X-CSRF-Token": valid_csrf}
    )
    assert resp_good.status_code == 202


def test_path_traversal_prevention(sec_app, tmp_path):
    """Verify that directory traversal attempts via artifact endpoints return 400 or 404."""
    client = sec_app.test_client()
    store = sec_app.test_store

    run_id = "RUN-SEC-TRAVERSAL"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    store.create_run(run_id=run_id, ticker="HINDUNILVR", output_dir=str(run_dir))

    # Malicious filenames attempting traversal
    traversal_payloads = [
        "../../../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "/etc/passwd",
        "../run_manifest.json",
        "subdir/../../secret.txt",
        "manifest.json;cat /etc/passwd"
    ]

    for payload in traversal_payloads:
        resp = client.get(f"/api/investigations/{run_id}/artifacts/{payload}")
        assert resp.status_code in (400, 404), f"Payload '{payload}' was not blocked properly: status {resp.status_code}"


def test_html_autoescaping_for_untrusted_text(sec_app, tmp_path):
    """Verify that untrusted evidence text containing <script> is properly escaped in Jinja2."""
    client = sec_app.test_client()
    store = sec_app.test_store

    run_id = "RUN-XSS-TEST"
    store.create_run(run_id=run_id, ticker="HINDUNILVR")

    xss_payload = "<script>alert('XSS_ATTACK_EXCERPT');</script>"
    store.save_run_data(
        run_id=run_id,
        discovery={"1_The_Discovery": f"Finding with {xss_payload}"},
        evidence=[{
            "evidence_id": "EV-XSS",
            "source_title": f"Title {xss_payload}",
            "supporting_excerpt": xss_payload,
            "publisher": "Exchange",
            "source_type": "news"
        }]
    )
    store.update_run_status(run_id=run_id, status="SUCCEEDED", primary_finding=xss_payload)

    resp = client.get(f"/investigations/{run_id}")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")

    # Raw script tag must NOT be executed or unescaped in HTML
    assert "<script>alert('XSS_ATTACK_EXCERPT');</script>" not in html
    # Must be escaped
    assert "&lt;script&gt;alert(&#039;XSS_ATTACK_EXCERPT&#039;);&lt;/script&gt;" in html or "&#39;XSS_ATTACK_EXCERPT&#39;" in html or "&lt;script&gt;" in html


def test_api_keys_never_serialized_to_client(sec_app, mocker):
    """Verify that API keys or environment secrets are never serialized into HTML or JSON responses."""
    fake_key = "AIzaSyTEST_SECRET_KEY_FOR_TESTING_12345678"
    mocker.patch.object(create_app, "GEMINI_API_KEY", fake_key, create=True)
    import config
    mocker.patch.object(config, "GEMINI_API_KEY", fake_key)

    client = sec_app.test_client()

    endpoints_to_check = [
        "/",
        "/investigations/new",
        "/settings",
        "/api/health",
        "/api/diagnostics",
        "/investigations"
    ]

    for ep in endpoints_to_check:
        resp = client.get(ep)
        body = resp.data.decode("utf-8")
        assert fake_key not in body, f"Secret API key leaked in response for endpoint: {ep}"
