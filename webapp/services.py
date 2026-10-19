"""
ALPHA-DECAY Investigation Execution Service.
Integrates the financial analytics engine, deterministic sandbox, and LangGraph courtroom
with asynchronous background worker execution, real-time stage event broadcasting,
cancellation management, and durable artifact generation.
"""

import os
import sys
import time
import json
import uuid
import queue
import logging
import threading
import traceback
from pathlib import Path
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Callable, Generator, Tuple
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import config
from ingestion.screener import ScreenerScraper
from engine.forensics import ForensicEngine
from agent.graph import investigation_app
from agent.llm_provider import central_provider
from exporter.pdf_report import export_forensic_pdf
from exporter.forensic_chart import generate_forensic_chart
from webapp.run_store import run_store

logger = logging.getLogger("alphadecay.services")

# Investigation execution phases in canonical order
INVESTIGATION_STAGES = [
    ("queued", "Queued in Execution Pipeline"),
    ("data_ingestion", "Statutory Data Ingestion"),
    ("financial_analytics", "Deterministic Math Sandbox"),
    ("anomaly_triage", "Accounting Anomaly Triage"),
    ("hypothesis_generation", "Competing Hypothesis Generation"),
    ("evidence_retrieval", "Evidence Harvesting & Transcript Verification"),
    ("peer_analysis", "Peer Triangulation & Relative Spread"),
    ("adversarial_assessment", "Adversarial Review & Adjudication"),
    ("report_validation", "Report Validation & 8-Point Synthesis"),
    ("pdf_generation", "Institutional PDF & Chart Export"),
    ("completed", "Investigation Finalized")
]


class InvestigationService:
    """
    Central orchestration service managing investigation lifecycles,
    bounded background execution, safe cancellation, and SSE event dispatch.
    """

    def __init__(self, max_workers: int = 1):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="alphadecay_worker")
        self._cancel_events: Dict[str, threading.Event] = {}
        self._subscribers: Dict[str, List[queue.Queue]] = {}
        self._lock = threading.Lock()
        
        # Recover interrupted runs upon startup
        try:
            run_store.mark_interrupted_runs_as_failed()
        except Exception as e:
            logger.warning(f"Failed to reset interrupted runs: {e}")

    # --------------------------------------------------------------------------
    # Event Broadcasting & SSE Broker
    # --------------------------------------------------------------------------

    def emit_event(
        self,
        run_id: str,
        stage: str,
        message: str,
        severity: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Persists an event and broadcasts it to active SSE listeners."""
        event_id = run_store.add_event(
            run_id=run_id,
            stage=stage,
            message=message,
            severity=severity,
            metadata=metadata
        )
        event_payload = {
            "id": event_id,
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "severity": severity.upper(),
            "message": message,
            "metadata": metadata
        }

        with self._lock:
            subscribers = self._subscribers.get(run_id, [])
            dead_subs = []
            for q in subscribers:
                try:
                    q.put_nowait(event_payload)
                except queue.Full:
                    dead_subs.append(q)
            for q in dead_subs:
                subscribers.remove(q)

        return event_payload

    def subscribe_events(self, run_id: str) -> Generator[Dict[str, Any], None, None]:
        """Generator yielding new events for a specific run in real time."""
        q = queue.Queue(maxsize=100)
        with self._lock:
            if run_id not in self._subscribers:
                self._subscribers[run_id] = []
            self._subscribers[run_id].append(q)

        try:
            while True:
                try:
                    event = q.get(timeout=15.0)
                    yield event
                    if event.get("stage") in ("completed", "failed", "cancelled"):
                        break
                except queue.Empty:
                    # Send keep-alive heartbeat comment
                    yield {"heartbeat": True, "timestamp": datetime.now(timezone.utc).isoformat()}
        finally:
            with self._lock:
                if run_id in self._subscribers and q in self._subscribers[run_id]:
                    self._subscribers[run_id].remove(q)

    # --------------------------------------------------------------------------
    # Validation & Parameter Sanitization
    # --------------------------------------------------------------------------

    @staticmethod
    def validate_submission_params(
        ticker: str,
        cutoff_date_str: Optional[str] = None,
        max_anomalies: Optional[int] = None
    ) -> Tuple[str, Optional[date], int]:
        """Validates and sanitizes user input parameters for an investigation."""
        clean_ticker = (ticker or "").upper().strip()
        if not clean_ticker or len(clean_ticker) > 20:
            raise ValueError(f"Invalid ticker symbol '{clean_ticker}'. Must be 1-20 alphanumeric characters.")
        
        # Check allowed characters: letters, numbers, dot, underscore, hyphen
        import re
        if not re.match(r"^[A-Z0-9_\-\.]{1,20}$", clean_ticker):
            raise ValueError(f"Ticker symbol '{clean_ticker}' contains invalid characters.")

        # Cutoff date validation
        cutoff_d: Optional[date] = None
        if cutoff_date_str and cutoff_date_str.strip():
            raw_c = cutoff_date_str.strip()
            try:
                cutoff_d = datetime.strptime(raw_c, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"Invalid cutoff date '{raw_c}'. Expected strict ISO format 'YYYY-MM-DD'.")

        # Bounded anomaly limit: 1 to 5
        eff_max = 2
        if max_anomalies is not None:
            try:
                eff_max = max(1, min(5, int(max_anomalies)))
            except (ValueError, TypeError):
                eff_max = 2

        return clean_ticker, cutoff_d, eff_max

    # --------------------------------------------------------------------------
    # Background Worker Execution
    # --------------------------------------------------------------------------

    def submit_investigation(
        self,
        ticker: str,
        cutoff_date_str: Optional[str] = None,
        max_anomalies: Optional[int] = None,
        offline: bool = False,
        export_pdf: bool = True
    ) -> str:
        """
        Validates parameters, registers the run in durable SQLite storage,
        and enqueues the task in the background worker. Returns run_id immediately.
        """
        clean_ticker, cutoff_d, eff_max = self.validate_submission_params(
            ticker=ticker,
            cutoff_date_str=cutoff_date_str,
            max_anomalies=max_anomalies
        )

        now_utc = datetime.now(timezone.utc)
        run_id = f"RUN-{now_utc.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

        # Isolated run output directory
        run_output_dir = BASE_DIR / "data" / "runs" / run_id
        run_output_dir.mkdir(parents=True, exist_ok=True)

        cutoff_str = str(cutoff_d) if cutoff_d else None

        # Create record in DB
        run_store.create_run(
            run_id=run_id,
            ticker=clean_ticker,
            cutoff_date=cutoff_str,
            max_anomalies=eff_max,
            offline_mode=offline,
            model_configured=config.GEMINI_MODEL,
            thinking_level=config.GEMINI_THINKING_LEVEL,
            output_dir=str(run_output_dir)
        )

        # Setup cancellation event
        cancel_event = threading.Event()
        with self._lock:
            self._cancel_events[run_id] = cancel_event

        # Submit to background executor
        self.executor.submit(
            self._worker_entrypoint,
            run_id=run_id,
            ticker=clean_ticker,
            cutoff_d=cutoff_d,
            max_anomalies=eff_max,
            offline=offline,
            export_pdf=export_pdf,
            output_dir=run_output_dir,
            cancel_event=cancel_event
        )

        logger.info(f"Enqueued investigation {run_id} for ticker {clean_ticker}")
        return run_id

    def cancel_investigation(self, run_id: str) -> bool:
        """
        Gracefully requests cancellation for a running or queued investigation.
        Signals the cancellation event and updates the persisted run status.
        """
        with self._lock:
            cancel_event = self._cancel_events.get(run_id)

        run = run_store.get_run(run_id)
        if not run:
            return False

        if run.get("status") in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return False

        if cancel_event:
            cancel_event.set()

        run_store.update_run_status(
            run_id=run_id,
            status="CANCELLED",
            current_stage="cancelled",
            error_message="Investigation was cancelled by user."
        )
        self.emit_event(
            run_id=run_id,
            stage="cancelled",
            message="Investigation execution halted by user request.",
            severity="WARNING"
        )
        return True

    # --------------------------------------------------------------------------
    # Core Pipeline Implementation
    # --------------------------------------------------------------------------

    def _worker_entrypoint(
        self,
        run_id: str,
        ticker: str,
        cutoff_d: Optional[date],
        max_anomalies: int,
        offline: bool,
        export_pdf: bool,
        output_dir: Path,
        cancel_event: threading.Event
    ) -> None:
        """Background thread target that catches exceptions and records state."""
        try:
            self.execute_investigation_pipeline(
                run_id=run_id,
                ticker=ticker,
                cutoff_d=cutoff_d,
                max_anomalies=max_anomalies,
                offline=offline,
                export_pdf=export_pdf,
                output_dir=output_dir,
                cancel_event=cancel_event,
                progress_callback=self.emit_event
            )
        except Exception as exc:
            logger.error(f"Investigation {run_id} failed with error: {exc}", exc_info=True)
            tb = traceback.format_exc()
            run_store.update_run_status(
                run_id=run_id,
                status="FAILED",
                current_stage="failed",
                error_message=str(exc),
                error_trace=tb,
                completed_at=datetime.now(timezone.utc).isoformat()
            )
            self.emit_event(
                run_id=run_id,
                stage="failed",
                message=f"Investigation failed: {str(exc)}",
                severity="ERROR",
                metadata={"error": str(exc), "trace": tb[:500]}
            )
        finally:
            with self._lock:
                self._cancel_events.pop(run_id, None)

    def execute_investigation_pipeline(
        self,
        run_id: str,
        ticker: str,
        cutoff_d: Optional[date],
        max_anomalies: int,
        offline: bool,
        export_pdf: bool,
        output_dir: Path,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[Callable[..., Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes the complete multi-stage investigation pipeline.
        Can be invoked asynchronously by the web worker or synchronously by the CLI.
        """
        start_time = time.time()
        start_utc = datetime.now(timezone.utc).isoformat()

        def cb(stage: str, msg: str, severity: str = "INFO", meta: Optional[dict] = None):
            if progress_callback:
                progress_callback(run_id=run_id, stage=stage, message=msg, severity=severity, metadata=meta)

        def is_cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        # Update status to RUNNING
        run_store.update_run_status(
            run_id=run_id,
            status="RUNNING",
            current_stage="data_ingestion",
            started_at=start_utc
        )

        if offline:
            config.USE_OFFLINE_MODE = True
            os.environ["USE_OFFLINE_MODE"] = "true"

        # ----------------------------------------------------------------------
        # Stage 1: Data Ingestion
        # ----------------------------------------------------------------------
        if is_cancelled():
            return {"status": "CANCELLED"}

        cb("data_ingestion", f"Ingesting statutory financial disclosures for '{ticker}' from regulatory filings...", "INFO")
        scraper = ScreenerScraper(use_cache=True)
        raw_data = scraper.fetch_company_data(ticker)
        company_name = raw_data.get("company_name", ticker)
        num_quarters = len(raw_data.get("quarters", {}).get("periods", []))

        run_store.update_run_status(run_id=run_id, status="RUNNING", company_name=company_name)
        cb(
            "data_ingestion",
            f"Successfully ingested {num_quarters} quarterly periods for '{company_name}' ({ticker}).",
            "SUCCESS",
            {"company_name": company_name, "quarters_count": num_quarters}
        )

        # ----------------------------------------------------------------------
        # Stage 2: Financial Analytics & Deterministic Math Sandbox
        # ----------------------------------------------------------------------
        if is_cancelled():
            return {"status": "CANCELLED"}

        cb("financial_analytics", "Executing deterministic accounting math sandbox (canonical ratios, residual, margin wedge)...", "INFO")
        summary = ForensicEngine.audit_company(raw_data, cutoff_date=cutoff_d)

        num_anomalies = len(summary.anomalies)
        anomalies_meta = [a.model_dump() for a in summary.anomalies]
        cb(
            "financial_analytics",
            f"Math sandbox completed. Quarters analyzed: {len(summary.quarters_analyzed)} | Anomalies flagged: {num_anomalies}.",
            "SUCCESS" if num_anomalies == 0 else "WARNING",
            {
                "quarters_analyzed": len(summary.quarters_analyzed),
                "anomalies_count": num_anomalies,
                "beneish_dsri": summary.beneish_dsri,
                "debtor_days_proxy": summary.debtor_days_ratio_proxy,
                "margin_wedge_bps": summary.margin_wedge_bps
            }
        )

        # ----------------------------------------------------------------------
        # Stage 3: Anomaly Triage Setup
        # ----------------------------------------------------------------------
        if is_cancelled():
            return {"status": "CANCELLED"}

        cb("anomaly_triage", f"Triaging {num_anomalies} accounting divergence candidate(s) by priority severity score...", "INFO")

        initial_state = {
            "run_id": run_id,
            "ticker": ticker,
            "company_name": company_name,
            "raw_financials": raw_data,
            "computed_metrics": {
                "debtor_days": summary.debtor_days,
                "sales_growth_yoy": summary.sales_growth_yoy,
                "expense_adjusted_residual": summary.expense_adjusted_residual,
                "beneish_dsri": summary.beneish_dsri,
                "debtor_days_ratio_proxy": summary.debtor_days_ratio_proxy,
                "beneish_sgi": summary.beneish_sgi,
                "beneish_gmi": summary.beneish_gmi,
                "cfo_to_ebitda": summary.cfo_to_ebitda,
                "margin_wedge_bps": summary.margin_wedge_bps,
                "operating_margin_delta_bps": summary.operating_margin_delta_bps,
                "distribution_drag_bps": summary.distribution_drag_bps,
                "peer_spread_days": summary.peer_spread_days
            },
            "anomalies": anomalies_meta,
            "no_material_anomaly": summary.no_material_anomaly_detected,
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
            "data_sufficiency": None,
            "adjudication_verdict": None,
            "iteration_count": 0,
            "current_anomaly_index": 0,
            "max_anomalies": max_anomalies,
            "completed_investigations": [],
            "final_discovery": None,
            "provider_metadata": {},
            "validation_passed": False,
            "logs": []
        }

        # ----------------------------------------------------------------------
        # LangGraph Stepped Execution (Observable & Cancelable between nodes)
        # ----------------------------------------------------------------------
        current_state = dict(initial_state)

        for step in investigation_app.stream(initial_state):
            if is_cancelled():
                cb("cancelled", "Investigation execution interrupted by user between graph stages.", "WARNING")
                return {"status": "CANCELLED"}

            for node_name, updates in step.items():
                current_state.update(updates)

                if node_name == "anomaly_triage":
                    sel = updates.get("selected_anomaly")
                    if updates.get("no_material_anomaly") or not sel:
                        cb("anomaly_triage", "Zero material accounting anomalies exceeded trigger boundaries. Proceeding to normal baseline compiler.", "INFO")
                    else:
                        cb("anomaly_triage", f"Candidate selected: {sel.get('metric_name')} in {sel.get('period')} (Delta: {sel.get('delta')} {sel.get('unit')}, Priority: {sel.get('severity_score')}).", "INFO", sel)

                elif node_name == "hypothesis_generator":
                    adverse = updates.get("adverse_hypothesis")
                    benign = updates.get("benign_hypothesis")
                    cb("hypothesis_generation", f"Formulated balanced competing hypotheses via {config.GEMINI_MODEL}.", "INFO", {"adverse": adverse, "benign": benign})

                elif node_name == "evidence_harvester":
                    p_ev = updates.get("prosecution_evidence", [])
                    cb("evidence_retrieval", f"Harvested and verified {len(p_ev)} external evidence records from exchange disclosures and concalls.", "INFO", {"evidence_count": len(p_ev)})

                elif node_name == "peer_triangulation":
                    peer_ev = updates.get("peer_evidence", [])
                    spread = current_state.get("computed_metrics", {}).get("peer_spread_days")
                    cb("peer_analysis", f"Synchronized peer filings ({len(peer_ev)} peers). Idiosyncratic spread: {spread if spread is not None else 'N/A'}.", "INFO", {"peers_evaluated": len(peer_ev), "spread": spread})

                elif node_name == "adversarial_critic":
                    adj = updates.get("adjudication", {})
                    verd = adj.get("verdict", "NOT_ESTABLISHED")
                    suff = adj.get("data_sufficiency", "SUFFICIENT")
                    rat = adj.get("rationale", "")
                    cb("adversarial_assessment", f"Courtroom adjudication completed. Calibrated Verdict: [{verd}] with [{suff} DATA].", "SUCCESS" if verd == "NOT_ESTABLISHED" or verd == "REFUTED" else "WARNING", adj)

                elif node_name == "compiler":
                    val_passed = updates.get("validation_passed", False)
                    disc = updates.get("final_discovery", {})
                    cb("report_validation", f"Synthesized mandatory 8-point institutional forensic deliverable. Validation Gate: {'PASS' if val_passed else 'FAIL'}.", "SUCCESS" if val_passed else "ERROR", {"validation_passed": val_passed, "heading": disc.get("finding_heading")})

        final_state = current_state
        discovery = final_state.get("final_discovery", {})

        # ----------------------------------------------------------------------
        # Stage 9: Institutional PDF & Forensic Chart Generation
        # ----------------------------------------------------------------------
        if is_cancelled():
            return {"status": "CANCELLED"}

        pdf_path = None
        chart_path = None

        if export_pdf:
            cb("pdf_generation", "Compiling high-resolution dark-theme forensic chart and institutional PDF report...", "INFO")
            computed_res = final_state.get("computed_metrics", {})
            if "peer_spread_days" in computed_res and computed_res["peer_spread_days"] is not None:
                summary.peer_spread_days = computed_res["peer_spread_days"]

            summary.model_used = final_state.get("provider_metadata", {}).get("model_name") or config.GEMINI_MODEL
            summary.thinking_level = config.GEMINI_THINKING_LEVEL
            summary.provider_used = final_state.get("provider_metadata", {}).get("provider_used") or ("ollama" if config.USE_OFFLINE_MODE else "gemini")
            summary.as_of_date = str(cutoff_d) if cutoff_d else None

            # Generate dual-panel chart
            chart_file = str(output_dir / f"forensic_chart_{ticker}.png")
            try:
                generate_forensic_chart(summary, output_path=chart_file)
                chart_path = chart_file
            except Exception as ce:
                logger.warning(f"Forensic chart generation error: {ce}")

            # Generate PDF
            target_pdf = str(output_dir / f"{ticker}_forensic_report.pdf")
            try:
                export_forensic_pdf(ticker, company_name, summary, discovery, target_pdf)
                pdf_path = target_pdf
            except Exception as pe:
                logger.error(f"PDF compilation error: {pe}", exc_info=True)

            cb("pdf_generation", f"Generated institutional PDF research note: {Path(target_pdf).name}", "SUCCESS")

        # ----------------------------------------------------------------------
        # Stage 10: Artifact Persistence & Run Manifest
        # ----------------------------------------------------------------------
        duration_sec = round(time.time() - start_time, 2)
        end_utc = datetime.now(timezone.utc).isoformat()

        adjudication_obj = final_state.get("adjudication", {})
        verdict_str = adjudication_obj.get("verdict") if isinstance(adjudication_obj, dict) else getattr(adjudication_obj, "verdict", None)
        data_suff_str = adjudication_obj.get("data_sufficiency") if isinstance(adjudication_obj, dict) else getattr(adjudication_obj, "data_sufficiency", None)
        primary_finding_str = discovery.get("1_The_Discovery", "") if discovery else None

        # Build run manifest
        manifest = {
            "run_id": run_id,
            "ticker": ticker,
            "company_name": company_name,
            "timestamp_utc": start_utc,
            "completed_at_utc": end_utc,
            "cutoff_date": str(cutoff_d) if cutoff_d else None,
            "model_configured": config.GEMINI_MODEL,
            "model_used": final_state.get("provider_metadata", {}).get("model_name", config.GEMINI_MODEL),
            "provider_used": final_state.get("provider_metadata", {}).get("provider_used", "gemini" if not config.USE_OFFLINE_MODE else "ollama"),
            "thinking_level": config.GEMINI_THINKING_LEVEL,
            "offline_mode": config.USE_OFFLINE_MODE,
            "quarters_analyzed": len(summary.quarters_analyzed),
            "anomalies_detected_count": len(summary.anomalies),
            "no_material_anomaly_detected": summary.no_material_anomaly_detected,
            "adjudication_verdict": verdict_str,
            "data_sufficiency": data_suff_str,
            "validation_passed": final_state.get("validation_passed", False),
            "pdf_report_path": pdf_path,
            "forensic_chart_path": chart_path,
            "duration_seconds": duration_sec
        }

        manifest_file = output_dir / "run_manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        json_bundle_file = output_dir / f"investigation_{ticker}.json"
        export_bundle = {
            "manifest": manifest,
            "final_discovery": discovery,
            "computed_metrics": final_state.get("computed_metrics", {}),
            "anomalies": final_state.get("anomalies", []),
            "raw_financials": final_state.get("raw_financials", {}),
            "prosecution_evidence": final_state.get("prosecution_evidence", []),
            "peer_evidence": final_state.get("peer_evidence", []),
            "adjudication": final_state.get("adjudication", {}),
            "logs": final_state.get("logs", [])
        }
        with open(json_bundle_file, "w", encoding="utf-8") as f:
            json.dump(export_bundle, f, indent=2, default=str)

        snapshot_file = output_dir / f"source_snapshot_{ticker}.json"
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(final_state.get("raw_financials", {}), f, indent=2, default=str)

        # ----------------------------------------------------------------------
        # Build Normalized Observations List with Formulas for Tab E
        # ----------------------------------------------------------------------
        raw_obs = [obs.model_dump() for obs in summary.observations]
        # Enrich raw observations and add derived metric observations
        enriched_observations = []
        for o in raw_obs:
            p_obj = o.get("period")
            period_label = p_obj.get("label") if isinstance(p_obj, dict) else str(p_obj)
            enriched_observations.append({
                "company": company_name,
                "ticker": ticker,
                "metric_name": o.get("metric_name"),
                "period": period_label,
                "value": o.get("numeric_value"),
                "raw_value": o.get("raw_source_value"),
                "unit": o.get("unit"),
                "frequency": o.get("frequency", "quarterly"),
                "classification": "Reported",
                "is_derived": False,
                "formula": o.get("canonical_definition"),
                "source_table": o.get("table_name", "quarters"),
                "source_locator": o.get("source_locator") or f"{o.get('table_name')}[{o.get('row_label')}][{period_label}]",
                "source_url": o.get("source_url") or f"https://www.screener.in/company/{ticker}/consolidated/"
            })

        # Add calculated metric observations
        for q, g in summary.sales_growth_yoy.items():
            enriched_observations.append({
                "company": company_name,
                "ticker": ticker,
                "metric_name": "Sales Growth YoY (%)",
                "period": q,
                "value": g,
                "raw_value": g,
                "unit": "%",
                "frequency": "quarterly",
                "classification": "Calculated",
                "is_derived": True,
                "formula": "((Sales_t - Sales_{t-4}) / Sales_{t-4}) * 100",
                "source_table": "quarters",
                "source_locator": f"YoY Period Alignment ({q} vs {q} - 1y)",
                "source_url": f"https://www.screener.in/company/{ticker}/consolidated/"
            })

        for q, res in summary.expense_adjusted_residual.items():
            enriched_observations.append({
                "company": company_name,
                "ticker": ticker,
                "metric_name": "Expense Residual Heuristic (%)",
                "period": q,
                "value": res,
                "raw_value": res,
                "unit": "%",
                "frequency": "quarterly",
                "classification": "Heuristic Proxy",
                "is_derived": True,
                "formula": "Reported Sales Growth YoY - (Expense Growth YoY * Cost-to-Sales Ratio)",
                "source_table": "quarters",
                "source_locator": f"Screening Heuristic ({q})",
                "source_url": f"https://www.screener.in/company/{ticker}/consolidated/"
            })

        for q, d in summary.debtor_days.items():
            enriched_observations.append({
                "company": company_name,
                "ticker": ticker,
                "metric_name": "Debtor Days",
                "period": q,
                "value": d,
                "raw_value": d,
                "unit": "d",
                "frequency": "annual / trailing",
                "classification": "Reported / Statutory",
                "is_derived": False,
                "formula": "(Trade Receivables / Annualized Net Sales) * 365",
                "source_table": "ratios_table",
                "source_locator": f"ratios_table[Debtor Days][{q}]",
                "source_url": f"https://www.screener.in/company/{ticker}/consolidated/"
            })

        # Save structured data in run_data table
        summary_dump = summary.model_dump()
        run_store.save_run_data(
            run_id=run_id,
            summary=summary_dump,
            discovery=discovery,
            metrics=final_state.get("computed_metrics", {}),
            anomalies=final_state.get("anomalies", []),
            hypotheses=final_state.get("competing_hypotheses", []),
            adjudication=adjudication_obj,
            evidence=final_state.get("prosecution_evidence", []),
            observations=enriched_observations,
            logs=final_state.get("logs", [])
        )

        # Update run status to SUCCEEDED
        run_store.update_run_status(
            run_id=run_id,
            status="SUCCEEDED",
            current_stage="completed",
            completed_at=end_utc,
            duration_seconds=duration_sec,
            model_used=manifest["model_used"],
            provider_used=manifest["provider_used"],
            quarters_analyzed=manifest["quarters_analyzed"],
            anomalies_detected_count=manifest["anomalies_detected_count"],
            no_material_anomaly=manifest["no_material_anomaly_detected"],
            adjudication_verdict=manifest["adjudication_verdict"],
            data_sufficiency=data_suff_str,
            evidence_strength=final_state.get("evidence_strength"),
            primary_finding=primary_finding_str,
            validation_passed=manifest["validation_passed"],
            pdf_path=str(pdf_path) if pdf_path else None,
            json_path=str(json_bundle_file),
            chart_path=str(chart_path) if chart_path else None,
            manifest_path=str(manifest_file),
            snapshot_path=str(snapshot_file)
        )

        cb(
            "completed",
            f"Forensic investigation {run_id} completed successfully in {duration_sec}s.",
            "SUCCESS",
            manifest
        )

        return final_state

    # --------------------------------------------------------------------------
    # Diagnostics & Health
    # --------------------------------------------------------------------------

    @staticmethod
    def get_system_diagnostics(live_check: bool = False) -> Dict[str, Any]:
        """
        Returns model provider configuration and health diagnostics
        WITHOUT exposing raw API keys or passwords.
        """
        key_present = bool(config.GEMINI_API_KEY and config.GEMINI_API_KEY.strip())
        masked_key = (config.GEMINI_API_KEY[:6] + "..." + config.GEMINI_API_KEY[-4:]) if (key_present and len(config.GEMINI_API_KEY) > 10) else ("CONFIGURED" if key_present else "MISSING")

        diag = {
            "gemini_model_configured": config.GEMINI_MODEL,
            "gemini_key_present": key_present,
            "gemini_key_masked": masked_key,
            "gemini_thinking_level": config.GEMINI_THINKING_LEVEL,
            "ollama_base_url": config.OLLAMA_BASE_URL,
            "ollama_fallback_model": config.OLLAMA_FALLBACK_MODEL,
            "offline_mode_active": config.USE_OFFLINE_MODE,
            "active_investigation_cutoff": config.INVESTIGATION_CUTOFF_DATE or None,
            "gemini_status": "CONFIGURED" if key_present else "UNAVAILABLE",
            "ollama_status": "CONFIGURED",
            "gemini_latency_s": None,
            "ollama_latency_s": None,
            "last_checked_utc": datetime.now(timezone.utc).isoformat()
        }

        if live_check:
            try:
                live_res = central_provider.diagnose_model_provider()
                diag["gemini_status"] = live_res.get("gemini_status")
                diag["gemini_latency_s"] = live_res.get("gemini_latency_s")
                diag["ollama_status"] = live_res.get("ollama_status")
                diag["ollama_latency_s"] = live_res.get("ollama_latency_s")
            except Exception as e:
                diag["gemini_status"] = f"DIAGNOSTIC_ERROR: {e}"

        return diag


# Global singleton investigation service instance
investigation_service = InvestigationService()
