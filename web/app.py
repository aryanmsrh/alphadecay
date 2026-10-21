import json
import os
import secrets
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    stream_with_context,
    url_for,
)

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from archive import archive
from agent.pipeline import run_investigation
from agent.llm import LLM

investigation_events: Dict[str, List[Dict[str, Any]]] = {}


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    web_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(web_dir / "templates"),
        static_folder=str(web_dir / "static"),
        static_url_path="/static",
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
            "model": f"{config.GEMINI_MODEL} / {config.OLLAMA_MODEL}",
            "ready": True,
            "base_url": config.OLLAMA_BASE_URL,
        }
        return {
            "csrf_token": session["csrf_token"],
            "system_health": health,
            "track_c_universe": config.TRACK_C_NIFTY50,
            "gemini_model": config.GEMINI_MODEL,
            "ollama_model": config.OLLAMA_MODEL,
        }

    @app.route("/")
    def index():
        metrics = archive.get_metrics()
        recent_runs = archive.list_reports(limit=10)
        return render_template("index.html", metrics=metrics, recent_runs=recent_runs)

    @app.route("/new")
    @app.route("/investigations/new")
    def new_investigation_page():
        return render_template("new_investigation.html")

    @app.route("/history")
    @app.route("/investigations/history")
    def investigations_history_page():
        search_query = request.args.get("search", "").strip().lower()
        status_filter = request.args.get("status", "").strip().upper()
        ticker_filter = request.args.get("ticker", "").strip().upper()

        page = max(1, int(request.args.get("page", 1)))
        per_page = 15

        all_reports = archive.list_reports(limit=500)
        filtered = []
        for r in all_reports:
            if status_filter and r.get("status") != status_filter:
                continue
            if ticker_filter and r.get("ticker") != ticker_filter:
                continue
            if search_query:
                combined = f"{r.get('ticker', '')} {r.get('company_name', '')} {r.get('hypothesis', '')}".lower()
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
            ticker_filter=ticker_filter,
        )

    @app.route("/settings")
    def settings_page():
        do_live = request.args.get("live") == "true"
        ollama_status = "CONFIGURED"
        ollama_latency = None

        if do_live:
            t0 = datetime.now()
            try:
                res = LLM(model=config.OLLAMA_MODEL)._generate_ollama('Reply with strictly valid JSON: {"status": "ok"}')
                if res:
                    ollama_status = "OK"
                    ollama_latency = round((datetime.now() - t0).total_seconds(), 2)
                else:
                    ollama_status = "UNAVAILABLE"
            except Exception:
                ollama_status = "UNAVAILABLE"

        diagnostics = {
            "ollama_status": ollama_status,
            "ollama_base_url": config.OLLAMA_BASE_URL,
            "ollama_model": config.OLLAMA_MODEL,
            "ollama_latency_s": ollama_latency,
            "server_host": request.host,
            "data_dir": str(config.DATA_DIR),
        }

        return render_template("settings.html", diagnostics=diagnostics)

    @app.route("/architecture")
    @app.route("/guide")
    def architecture_page():
        return render_template("architecture.html")

    @app.route("/api/investigate", methods=["POST"])
    @app.route("/api/investigation/create", methods=["POST"])
    def api_create_investigation():
        if request.is_json:
            data = request.get_json() or {}
            ticker = data.get("ticker", "").strip().upper()
            hypothesis = data.get("hypothesis", "").strip()
            raw_count = data.get("anomaly_count", 1)
            provider = (data.get("provider") or config.DEFAULT_PROVIDER).strip().lower()
        else:
            ticker = request.form.get("ticker", "").strip().upper()
            hypothesis = request.form.get("hypothesis", "").strip()
            raw_count = request.form.get("anomaly_count", 1)
            provider = (request.form.get("provider") or config.DEFAULT_PROVIDER).strip().lower()

        try:
            anomaly_count = max(1, min(int(raw_count), 5))
        except (ValueError, TypeError):
            anomaly_count = 1

        if not ticker:
            return jsonify({"error": "Ticker symbol is required"}), 400

        run_id = uuid.uuid4().hex[:8]
        active_model = config.GEMINI_MODEL if "gemini" in provider else config.OLLAMA_MODEL
        investigation_events[run_id] = [
            {
                "step": "INIT",
                "message": f"Queued analysis for {ticker} (targeting {anomaly_count} anomaly via {active_model})",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]

        initial_record = {
            "run_id": run_id,
            "ticker": ticker,
            "company_name": ticker,
            "hypothesis": hypothesis or f"Analysis for {ticker}",
            "anomalies_requested": anomaly_count,
            "status": "RUNNING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider": active_model,
        }
        archive.save_report(initial_record)

        def event_handler(evt: Dict[str, Any]):
            if run_id not in investigation_events:
                investigation_events[run_id] = []
            investigation_events[run_id].append(evt)

        def runner(t: str, h: str, r_id: str, count: int, prov: str):
            try:
                res = run_investigation(
                    t,
                    hypothesis=h if h else None,
                    run_id=r_id,
                    anomaly_count=count,
                    event_callback=event_handler,
                    provider=prov,
                )
                res["status"] = "COMPLETED"
                archive.save_report(res)
            except Exception as e:
                err_msg = str(e)
                err_type = type(e).__name__

                if "timed out" in err_msg.lower():
                    if "concall" in err_msg.lower():
                        display_err = f"Concall transcript download timed out: {err_msg}"
                    elif "tavily" in err_msg.lower():
                        display_err = f"Tavily search API timed out: {err_msg}"
                    elif "gemini" in err_msg.lower():
                        display_err = f"Gemini Cloud inference timed out: {err_msg}"
                    else:
                        display_err = f"Operation timed out: {err_msg}"
                elif "503" in err_msg:
                    display_err = f"Gemini Cloud high demand (503 Service Unavailable). Please retry or select another model: {err_msg}"
                else:
                    display_err = f"{err_type}: {err_msg}"

                event_handler({
                    "step": "ERROR",
                    "message": display_err,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                archive.update_status(r_id, "FAILED", error=display_err)

        thread = threading.Thread(target=runner, args=(ticker, hypothesis, run_id, anomaly_count, provider), daemon=True)
        thread.start()

        if request.is_json:
            return jsonify({"run_id": run_id, "status": "RUNNING", "ticker": ticker, "anomaly_count": anomaly_count, "provider": provider}), 202

        return redirect(url_for("investigation_detail_page", run_id=run_id))

    @app.route("/investigation/<run_id>")
    def investigation_detail_page(run_id: str):
        run = archive.get_report(run_id)
        if not run:
            abort(404)
        return render_template("investigation_detail.html", run=run)

    @app.route("/api/investigation/<run_id>/status")
    def api_investigation_status(run_id: str):
        run = archive.get_report(run_id)
        if not run:
            return jsonify({"error": "Run not found"}), 404
        return jsonify({
            "run_id": run_id,
            "status": run.get("status"),
            "provider": run.get("provider"),
            "error": run.get("error"),
        })

    @app.route("/api/investigation/<run_id>/events")
    def api_investigation_events(run_id: str):
        run = archive.get_report(run_id)
        status = run.get("status") if run else "UNKNOWN"
        events = investigation_events.get(run_id) or (run.get("events", []) if run else [])
        return jsonify({"run_id": run_id, "status": status, "events": events})

    @app.route("/api/investigation/<run_id>/stream")
    def api_investigation_stream(run_id: str):
        def generate():
            last_index = 0
            while True:
                events = investigation_events.get(run_id, [])
                if last_index < len(events):
                    for evt in events[last_index:]:
                        yield f"data: {json.dumps(evt)}\n\n"
                    last_index = len(events)

                run = archive.get_report(run_id)
                current_status = run.get("status") if run else "UNKNOWN"

                if current_status in ("COMPLETED", "FAILED"):
                    yield f"data: {json.dumps({'step': 'FINISHED', 'status': current_status})}\n\n"
                    break

                time.sleep(0.5)

        return Response(stream_with_context(generate()), mimetype="text/event-stream")

    @app.route("/api/investigation/<run_id>/pdf")
    def api_investigation_pdf(run_id: str):
        run = archive.get_report(run_id)
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
            download_name=f"{run.get('ticker')}_report.pdf",
        )

    @app.route("/api/investigation/<run_id>/delete", methods=["POST", "DELETE"])
    def api_investigation_delete(run_id: str):
        success = archive.delete_report(run_id)
        if run_id in investigation_events:
            investigation_events.pop(run_id, None)
        if request.is_json or request.method == "DELETE":
            return jsonify({"success": success, "run_id": run_id})
        return redirect(url_for("investigations_history_page"))

    return app


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AlphaDecay Web Application")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")), help="Port number")
    parser.add_argument("--debug", action="store_true", default=False, help="Enable debug mode")

    args = parser.parse_args()
    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
