"""
ALPHA-DECAY Flask Application Factory & Route Registration.
Provides browser endpoints, REST APIs, SSE real-time streaming,
safe artifact downloads, CSRF protection, and diagnostics.
"""

import os
import sys
import re
import secrets
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from flask import (
    Flask, render_template, request, jsonify, send_file,
    redirect, url_for, session, abort, Response, stream_with_context
)

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from config import TRACK_C_NIFTY50, PEER_MAPPING
from webapp.run_store import run_store, RunStore
from webapp.services import investigation_service, InvestigationService, INVESTIGATION_STAGES

logger = logging.getLogger("alphadecay.webapp")

# Safe artifact filename regex: alphanumeric, dash, underscore, dot ending in allowed extension
SAFE_ARTIFACT_RE = re.compile(r"^[a-zA-Z0-9_\-\.]+\.(pdf|json|png|txt)$")


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    """Application factory for ALPHA-DECAY Webapp."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static"
    )

    # Secret key for session management & CSRF
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
    app.config["JSON_SORT_KEYS"] = False
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    if test_config:
        app.config.update(test_config)

    # --------------------------------------------------------------------------
    # Security Headers & CSRF Middleware
    # --------------------------------------------------------------------------

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    @app.context_processor
    def inject_globals():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)

        health_quick = {
            "gemini_model": config.GEMINI_MODEL,
            "gemini_ready": bool(config.GEMINI_API_KEY),
            "ollama_model": config.OLLAMA_FALLBACK_MODEL,
            "offline_mode": config.USE_OFFLINE_MODE
        }
        return {
            "csrf_token": session["csrf_token"],
            "track_c_universe": TRACK_C_NIFTY50,
            "system_health": health_quick,
            "now_year": datetime.now(timezone.utc).year,
            "investigation_stages": INVESTIGATION_STAGES
        }

    @app.before_request
    def validate_csrf():
        # Skip CSRF check in test mode unless explicitly enforced
        if app.config.get("TESTING") and not app.config.get("ENFORCE_CSRF", False):
            return

        # Only enforce on state-changing methods
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            # Exclude endpoints if explicitly flagged or public APIs if needed
            token = (
                request.headers.get("X-CSRF-Token") or
                request.form.get("csrf_token") or
                (request.is_json and request.get_json(silent=True) and request.get_json(silent=True).get("csrf_token"))
            )
            expected_token = session.get("csrf_token")

            if not expected_token or not token or not secrets.compare_digest(token, expected_token):
                if request.is_json or request.path.startswith("/api/"):
                    return jsonify({"error": "Invalid or missing CSRF token"}), 403
                abort(403, description="CSRF token verification failed. Please refresh the page and try again.")

    # --------------------------------------------------------------------------
    # Page Routes
    # --------------------------------------------------------------------------

    @app.route("/")
    def index():
        """Main landing dashboard: overview metrics & recent investigations."""
        metrics = run_store.get_overview_metrics()
        recent_runs, total_count = run_store.list_runs(page=1, per_page=10)
        return render_template(
            "index.html",
            metrics=metrics,
            recent_runs=recent_runs,
            total_count=total_count,
            page_title="Forensic Intelligence Terminal"
        )

    @app.route("/investigations/new")
    def new_investigation_page():
        """New investigation submission form."""
        return render_template(
            "new_investigation.html",
            page_title="Launch New Investigation"
        )

    @app.route("/investigations")
    def investigations_history_page():
        """Investigation history list with search, filtering, and pagination."""
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 15, type=int)
        ticker = request.args.get("ticker", "").strip() or None
        status = request.args.get("status", "").strip() or None
        verdict = request.args.get("verdict", "").strip() or None
        search = request.args.get("search", "").strip() or None

        runs, total = run_store.list_runs(
            page=page,
            per_page=per_page,
            ticker=ticker,
            status=status,
            verdict=verdict,
            search=search
        )
        total_pages = max(1, (total + per_page - 1) // per_page)

        return render_template(
            "history.html",
            runs=runs,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            ticker_filter=ticker or "",
            status_filter=status or "",
            verdict_filter=verdict or "",
            search_query=search or "",
            page_title="Investigation History"
        )

    @app.route("/investigations/<run_id>")
    def investigation_detail_page(run_id: str):
        """Investigation detail workspace & real-time monitoring page."""
        run = run_store.get_run(run_id)
        if not run:
            abort(404, description=f"Investigation run '{run_id}' not found.")

        data = run_store.get_run_data(run_id) or {}
        events = run_store.get_events(run_id, limit=200)

        return render_template(
            "investigation_detail.html",
            run=run,
            data=data,
            events=events,
            page_title=f"{run.get('ticker')} // {run.get('company_name')} Audit"
        )

    @app.route("/settings")
    def settings_page():
        """Settings and Provider Diagnostics page."""
        live = request.args.get("live", "false").lower() in ("true", "1", "yes")
        diagnostics = investigation_service.get_system_diagnostics(live_check=live)
        return render_template(
            "settings.html",
            diagnostics=diagnostics,
            page_title="Settings & System Diagnostics"
        )

    # --------------------------------------------------------------------------
    # API Routes
    # --------------------------------------------------------------------------

    @app.route("/api/investigations", methods=["POST"])
    def api_create_investigation():
        """Submits a new investigation to the background executor."""
        data = request.get_json(silent=True) or request.form.to_dict() or {}

        ticker = data.get("ticker", "").strip()
        cutoff_date = data.get("cutoff_date", "").strip() or None
        max_anomalies = data.get("max_anomalies", 2)
        offline = str(data.get("offline", "")).lower() in ("true", "1", "yes")
        export_pdf = str(data.get("export_pdf", "true")).lower() in ("true", "1", "yes")

        try:
            run_id = investigation_service.submit_investigation(
                ticker=ticker,
                cutoff_date_str=cutoff_date,
                max_anomalies=max_anomalies,
                offline=offline,
                export_pdf=export_pdf
            )
            redirect_url = url_for("investigation_detail_page", run_id=run_id)
            if request.is_json:
                return jsonify({
                    "success": True,
                    "run_id": run_id,
                    "status": "QUEUED",
                    "redirect_url": redirect_url
                }), 202
            return redirect(redirect_url)
        except ValueError as val_err:
            if request.is_json:
                return jsonify({"error": str(val_err)}), 400
            abort(400, description=str(val_err))
        except Exception as e:
            logger.error(f"Failed to submit investigation: {e}", exc_info=True)
            if request.is_json:
                return jsonify({"error": f"Failed to submit investigation: {str(e)}"}), 500
            abort(500, description="Internal server error launching investigation.")

    @app.route("/api/investigations", methods=["GET"])
    def api_list_investigations():
        """Returns paginated list of investigations with query filters."""
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        ticker = request.args.get("ticker", "").strip() or None
        status = request.args.get("status", "").strip() or None
        verdict = request.args.get("verdict", "").strip() or None
        search = request.args.get("search", "").strip() or None

        runs, total = run_store.list_runs(
            page=page,
            per_page=per_page,
            ticker=ticker,
            status=status,
            verdict=verdict,
            search=search
        )
        return jsonify({
            "runs": runs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page)
        })

    @app.route("/api/investigations/<run_id>", methods=["GET"])
    def api_get_investigation(run_id: str):
        """Returns single investigation summary."""
        run = run_store.get_run(run_id)
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404
        return jsonify({"run": run})

    @app.route("/api/investigations/<run_id>/events", methods=["GET"])
    def api_get_events(run_id: str):
        """Returns list of events for a run, with optional since_id for polling."""
        run = run_store.get_run(run_id)
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        since_id = request.args.get("since_id", type=int)
        events = run_store.get_events(run_id, since_id=since_id)
        return jsonify({
            "run_id": run_id,
            "status": run.get("status"),
            "current_stage": run.get("current_stage"),
            "events": events
        })

    @app.route("/api/investigations/<run_id>/events/stream", methods=["GET"])
    def api_stream_events(run_id: str):
        """Server-Sent Events (SSE) endpoint for real-time progress updates."""
        run = run_store.get_run(run_id)
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        def event_stream():
            import json
            for ev in investigation_service.subscribe_events(run_id):
                if ev.get("heartbeat"):
                    yield f": heartbeat {ev.get('timestamp')}\n\n"
                else:
                    yield f"data: {json.dumps(ev)}\n\n"

        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive"
            }
        )

    @app.route("/api/investigations/<run_id>/report", methods=["GET"])
    def api_get_report(run_id: str):
        """Returns final 8-point forensic report discovery."""
        run = run_store.get_run(run_id)
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        data = run_store.get_run_data(run_id) or {}
        return jsonify({
            "run_id": run_id,
            "ticker": run.get("ticker"),
            "company_name": run.get("company_name"),
            "status": run.get("status"),
            "adjudication_verdict": run.get("adjudication_verdict"),
            "data_sufficiency": run.get("data_sufficiency"),
            "discovery": data.get("discovery", {})
        })

    @app.route("/api/investigations/<run_id>/metrics", methods=["GET"])
    def api_get_metrics(run_id: str):
        """Returns structured computed metrics and time-series for interactive Chart.js charts."""
        run = run_store.get_run(run_id)
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        data = run_store.get_run_data(run_id) or {}
        summary = data.get("summary", {})
        metrics = data.get("metrics", {})

        quarters = summary.get("quarters_analyzed", [])
        sales_growth = summary.get("sales_growth_yoy", {})
        residual = summary.get("expense_adjusted_residual", {})
        debtor_days = summary.get("debtor_days", {})

        # Prepare chart series aligning with quarters
        sales_series = [sales_growth.get(q) for q in quarters]
        residual_series = [residual.get(q) for q in quarters]
        debtor_series = [debtor_days.get(q) for q in quarters]

        return jsonify({
            "run_id": run_id,
            "ticker": run.get("ticker"),
            "company_name": run.get("company_name"),
            "quarters": quarters,
            "series": {
                "sales_growth_yoy": sales_series,
                "expense_adjusted_residual": residual_series,
                "debtor_days": debtor_series
            },
            "metrics": metrics,
            "canonical_dsri": summary.get("beneish_dsri"),
            "debtor_days_proxy": summary.get("debtor_days_ratio_proxy"),
            "margin_wedge_bps": summary.get("margin_wedge_bps"),
            "peer_spread_days": summary.get("peer_spread_days"),
            "cfo_to_operating_profit": summary.get("cfo_to_operating_profit")
        })

    @app.route("/api/investigations/<run_id>/evidence", methods=["GET"])
    def api_get_evidence(run_id: str):
        """Returns structured evidence records and provenance metadata."""
        run = run_store.get_run(run_id)
        if not run:
            return jsonify({"error": f"Run '{run_id}' not found"}), 404

        data = run_store.get_run_data(run_id) or {}
        evidence_list = data.get("evidence", [])
        return jsonify({
            "run_id": run_id,
            "count": len(evidence_list),
            "evidence": evidence_list
        })

    @app.route("/api/investigations/<run_id>/artifacts/<artifact_name>", methods=["GET"])
    def api_download_artifact(run_id: str, artifact_name: str):
        """
        Safely serves generated artifacts (PDF, JSON, PNG) strictly belonging to run_id.
        Prevents directory traversal attacks and unauthorized file access.
        """
        # Validate run exists
        run = run_store.get_run(run_id)
        if not run:
            abort(404, description=f"Run '{run_id}' not found.")

        # Sanitize artifact filename
        clean_name = artifact_name.strip()
        if not SAFE_ARTIFACT_RE.match(clean_name) or ".." in clean_name or "/" in clean_name or "\\" in clean_name:
            abort(400, description="Invalid artifact filename or path traversal detected.")

        # Locate run directory
        run_output_dir = Path(run.get("output_dir") or (BASE_DIR / "data" / "runs" / run_id)).resolve()
        target_path = (run_output_dir / clean_name).resolve()

        # Strict containment check
        try:
            target_path.relative_to(run_output_dir)
        except ValueError:
            abort(403, description="Access to requested file path is forbidden.")

        if not target_path.exists() or not target_path.is_file():
            abort(404, description=f"Artifact '{clean_name}' does not exist for run '{run_id}'.")

        # Determine safe MIME type and disposition
        mime_types = {
            ".pdf": "application/pdf",
            ".json": "application/json",
            ".png": "image/png",
            ".txt": "text/plain"
        }
        suffix = target_path.suffix.lower()
        mimetype = mime_types.get(suffix, "application/octet-stream")

        as_attachment = request.args.get("download", "true").lower() in ("true", "1")
        return send_file(
            target_path,
            mimetype=mimetype,
            as_attachment=as_attachment,
            download_name=clean_name
        )

    @app.route("/api/investigations/<run_id>/cancel", methods=["POST"])
    def api_cancel_investigation(run_id: str):
        """Cancels an in-progress investigation safely."""
        success = investigation_service.cancel_investigation(run_id)
        if not success:
            run = run_store.get_run(run_id)
            if not run:
                return jsonify({"error": f"Run '{run_id}' not found"}), 404
            return jsonify({
                "error": f"Cannot cancel investigation in status '{run.get('status')}'."
            }), 400

        return jsonify({
            "success": True,
            "run_id": run_id,
            "status": "CANCELLED",
            "message": "Cancellation request acknowledged. Stopping subsequent graph stages."
        })

    @app.route("/api/health", methods=["GET"])
    def api_health():
        """Health check endpoint for application and model availability."""
        diag = investigation_service.get_system_diagnostics(live_check=False)
        return jsonify({
            "status": "HEALTHY",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gemini_model": diag.get("gemini_model_configured"),
            "gemini_key_present": diag.get("gemini_key_present"),
            "ollama_model": diag.get("ollama_fallback_model"),
            "offline_mode": diag.get("offline_mode_active")
        })

    @app.route("/api/diagnostics", methods=["GET"])
    def api_diagnostics():
        """Detailed system diagnostics with optional live connectivity ping."""
        live = request.args.get("live", "false").lower() in ("true", "1", "yes")
        diag = investigation_service.get_system_diagnostics(live_check=live)
        return jsonify(diag)

    # --------------------------------------------------------------------------
    # Error Handlers
    # --------------------------------------------------------------------------

    @app.errorhandler(400)
    def bad_request(error):
        msg = getattr(error, "description", "Bad Request")
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": msg}), 400
        return render_template("errors/400.html", message=msg), 400

    @app.errorhandler(403)
    def forbidden(error):
        msg = getattr(error, "description", "Forbidden")
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": msg}), 403
        return render_template("errors/403.html", message=msg), 403

    @app.errorhandler(404)
    def not_found(error):
        msg = getattr(error, "description", "Resource Not Found")
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": msg}), 404
        return render_template("errors/404.html", message=msg), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error on {request.path}: {error}", exc_info=True)
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html", message="An unexpected error occurred."), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)
