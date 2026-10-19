import os
import sys
import uuid
import secrets
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    redirect,
    url_for,
    session,
    abort
)

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from config import TRACK_C_NIFTY50
from webapp.run_store import run_store
from engine.investigator import investigate_company
from engine.llm import call_gemini, call_ollama


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static"
    )

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
    app.config["JSON_SORT_KEYS"] = False
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    if test_config:
        app.config.update(test_config)

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.context_processor
    def inject_globals():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)

        health = {
            "gemini_model": config.GEMINI_MODEL,
            "gemini_ready": bool(config.GEMINI_API_KEY) and not config.USE_OFFLINE_MODE,
            "ollama_model": config.OLLAMA_FALLBACK_MODEL,
            "offline_mode": config.USE_OFFLINE_MODE
        }
        return {
            "csrf_token": session["csrf_token"],
            "system_health": health,
            "track_c_universe": TRACK_C_NIFTY50
        }

    @app.route("/")
    def index():
        metrics = run_store.get_metrics()
        recent_runs = run_store.list_runs(limit=10)
        return render_template("index.html", metrics=metrics, recent_runs=recent_runs)

    @app.route("/new")
    def new_investigation_page():
        return render_template("new_investigation.html")

    @app.route("/history")
    def investigations_history_page():
        search_query = request.args.get("search", "").strip().lower()
        status_filter = request.args.get("status", "").strip().upper()
        verdict_filter = request.args.get("verdict", "").strip().upper()
        ticker_filter = request.args.get("ticker", "").strip().upper()

        page = max(1, int(request.args.get("page", 1)))
        per_page = 15

        all_runs = run_store.list_runs(limit=500)
        filtered = []
        for r in all_runs:
            if status_filter and r.get("status") != status_filter:
                continue
            if verdict_filter and (r.get("verdict") != verdict_filter and r.get("adjudication_verdict") != verdict_filter):
                continue
            if ticker_filter and r.get("ticker") != ticker_filter:
                continue
            if search_query:
                combined = f"{r.get('ticker', '')} {r.get('company_name', '')} {r.get('hypothesis', '')} {r.get('verdict', '')}".lower()
                if search_query not in combined:
                    continue
            filtered.append(r)

        total = len(filtered)
        total_pages = max(1, (total + per_page - 1) // per_page)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_runs = filtered[start_idx:end_idx]

        return render_template(
            "history.html",
            runs=page_runs,
            total=total,
            page=page,
            total_pages=total_pages,
            per_page=per_page,
            search_query=search_query,
            status_filter=status_filter,
            verdict_filter=verdict_filter,
            ticker_filter=ticker_filter
        )

    @app.route("/settings")
    def settings_page():
        do_live = request.args.get("live") == "true"
        gemini_status = "CONFIGURED" if config.GEMINI_API_KEY else "MISSING_KEY"
        gemini_latency = None
        ollama_status = "CONFIGURED"
        ollama_latency = None

        if do_live:
            if config.GEMINI_API_KEY and not config.USE_OFFLINE_MODE:
                t0 = datetime.now()
                try:
                    res = call_gemini("Reply with OK")
                    if res:
                        gemini_status = "OK"
                        gemini_latency = round((datetime.now() - t0).total_seconds(), 2)
                    else:
                        gemini_status = "FAILED"
                except Exception:
                    gemini_status = "FAILED"

            t0 = datetime.now()
            try:
                res = call_ollama("Reply with OK")
                if res:
                    ollama_status = "OK"
                    ollama_latency = round((datetime.now() - t0).total_seconds(), 2)
                else:
                    ollama_status = "UNAVAILABLE"
            except Exception:
                ollama_status = "UNAVAILABLE"

        masked_key = f"{config.GEMINI_API_KEY[:4]}...{config.GEMINI_API_KEY[-4:]}" if len(config.GEMINI_API_KEY) > 8 else "NOT_SET"

        diagnostics = {
            "gemini_status": gemini_status,
            "gemini_key_present": bool(config.GEMINI_API_KEY),
            "gemini_key_masked": masked_key,
            "gemini_model_configured": config.GEMINI_MODEL,
            "gemini_thinking_level": "HIGH",
            "gemini_latency_s": gemini_latency,
            "ollama_status": ollama_status,
            "ollama_base_url": config.OLLAMA_BASE_URL,
            "ollama_model": config.OLLAMA_FALLBACK_MODEL,
            "ollama_latency_s": ollama_latency
        }

        return render_template("settings.html", diagnostics=diagnostics)

    @app.route("/api/investigate", methods=["POST"])
    @app.route("/api/investigation/create", methods=["POST"])
    def api_create_investigation():
        if request.is_json:
            data = request.get_json() or {}
            ticker = data.get("ticker", "").strip().upper()
            hypothesis = data.get("hypothesis", "").strip()
        else:
            ticker = request.form.get("ticker", "").strip().upper()
            hypothesis = request.form.get("hypothesis", "").strip()

        if not ticker:
            return jsonify({"error": "Ticker symbol is required"}), 400

        run_id = uuid.uuid4().hex[:8]
        initial_record = {
            "run_id": run_id,
            "ticker": ticker,
            "company_name": ticker,
            "hypothesis": hypothesis or f"Investigate financial indicators and anomalies for {ticker}",
            "status": "RUNNING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider": "gemini" if (config.GEMINI_API_KEY and not config.USE_OFFLINE_MODE) else "ollama"
        }
        run_store.save_run(initial_record)

        def runner(t: str, h: str, r_id: str):
            try:
                res = investigate_company(t, hypothesis=h if h else None, run_id=r_id)
                res["status"] = "COMPLETED"
                res["adjudication_verdict"] = res.get("verdict")
                res["primary_finding"] = (
                    res.get("report", {}).get("1_The_Discovery")
                    or res.get("report", {}).get("verdict_summary")
                    or res.get("report", {}).get("1_Executive_Summary")
                )
                res["provider_used"] = res.get("provider", "gemini")
                run_store.save_run(res)
            except Exception as e:
                run_store.update_status(r_id, "FAILED", error=str(e))

        thread = threading.Thread(target=runner, args=(ticker, hypothesis, run_id), daemon=True)
        thread.start()

        if request.is_json:
            return jsonify({"run_id": run_id, "status": "RUNNING", "ticker": ticker}), 202

        return redirect(url_for("investigation_detail_page", run_id=run_id))

    @app.route("/investigation/<run_id>")
    def investigation_detail_page(run_id: str):
        run = run_store.get_run(run_id)
        if not run:
            abort(404)
        return render_template("investigation_detail.html", run=run)

    @app.route("/api/investigation/<run_id>/status")
    def api_investigation_status(run_id: str):
        run = run_store.get_run(run_id)
        if not run:
            return jsonify({"error": "Run not found"}), 404
        return jsonify({
            "run_id": run_id,
            "status": run.get("status"),
            "verdict": run.get("verdict"),
            "provider": run.get("provider"),
            "error": run.get("error")
        })

    @app.route("/api/investigation/<run_id>/chart")
    def api_investigation_chart(run_id: str):
        run = run_store.get_run(run_id)
        if not run:
            abort(404)
        raw_p = Path(run.get("chart_path") or f"data/runs/{run_id}/chart.png")
        chart_p = raw_p.resolve() if raw_p.is_absolute() else (BASE_DIR / raw_p).resolve()
        if not chart_p.exists():
            abort(404)
        return send_file(str(chart_p), mimetype="image/png")

    @app.route("/api/investigation/<run_id>/pdf")
    def api_investigation_pdf(run_id: str):
        run = run_store.get_run(run_id)
        if not run:
            abort(404)
        raw_p = Path(run.get("pdf_path") or f"data/runs/{run_id}/report.pdf")
        pdf_p = raw_p.resolve() if raw_p.is_absolute() else (BASE_DIR / raw_p).resolve()
        if not pdf_p.exists():
            abort(404)
        return send_file(
            str(pdf_p),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"{run.get('ticker')}_forensic_report.pdf"
        )

    return app
