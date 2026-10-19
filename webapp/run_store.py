"""
ALPHA-DECAY Durable Run Store & Event Persistence Layer.
SQLite-backed storage for investigation runs, real-time lifecycle events,
computed metrics, structured evidence provenance, and artifact references.
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("alphadecay.run_store")

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "alphadecay.db"


class RunStore:
    """
    Thread-safe SQLite store for investigation records, stage events, and artifacts.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def init_db(self) -> None:
        """Initializes tables and indices if not already present."""
        with self.get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS investigation_runs (
                run_id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                company_name TEXT,
                status TEXT NOT NULL,
                current_stage TEXT,
                cutoff_date TEXT,
                max_anomalies INTEGER DEFAULT 2,
                offline_mode INTEGER DEFAULT 0,
                model_configured TEXT,
                model_used TEXT,
                provider_used TEXT,
                thinking_level TEXT,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds REAL,
                quarters_analyzed INTEGER,
                anomalies_detected_count INTEGER DEFAULT 0,
                no_material_anomaly INTEGER DEFAULT 0,
                adjudication_verdict TEXT,
                data_sufficiency TEXT,
                evidence_strength TEXT,
                primary_finding TEXT,
                validation_passed INTEGER DEFAULT 0,
                error_message TEXT,
                error_trace TEXT,
                output_dir TEXT,
                pdf_path TEXT,
                json_path TEXT,
                chart_path TEXT,
                manifest_path TEXT,
                snapshot_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                stage TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'INFO',
                message TEXT NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY (run_id) REFERENCES investigation_runs(run_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS run_data (
                run_id TEXT PRIMARY KEY,
                summary_json TEXT,
                discovery_json TEXT,
                metrics_json TEXT,
                anomalies_json TEXT,
                hypotheses_json TEXT,
                adjudication_json TEXT,
                evidence_json TEXT,
                observations_json TEXT,
                logs_json TEXT,
                FOREIGN KEY (run_id) REFERENCES investigation_runs(run_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_runs_ticker ON investigation_runs(ticker);
            CREATE INDEX IF NOT EXISTS idx_runs_status ON investigation_runs(status);
            CREATE INDEX IF NOT EXISTS idx_runs_created_at ON investigation_runs(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_events_run_id ON run_events(run_id, id ASC);
            """)

    def mark_interrupted_runs_as_failed(self) -> int:
        """
        On application startup, safely marks any runs stuck in RUNNING or QUEUED
        from a prior process termination as FAILED with an explicit diagnostic note.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE investigation_runs
                SET status = 'FAILED',
                    error_message = 'Server process restarted while investigation was in progress.',
                    completed_at = ?,
                    updated_at = ?
                WHERE status IN ('RUNNING', 'QUEUED');
                """,
                (now, now)
            )
            count = cursor.rowcount
            if count > 0:
                logger.info(f"Marked {count} interrupted run(s) as FAILED upon startup.")
            return count

    def create_run(
        self,
        run_id: str,
        ticker: str,
        company_name: Optional[str] = None,
        cutoff_date: Optional[str] = None,
        max_anomalies: int = 2,
        offline_mode: bool = False,
        model_configured: Optional[str] = None,
        thinking_level: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a new run record with status QUEUED."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO investigation_runs (
                    run_id, ticker, company_name, status, current_stage,
                    cutoff_date, max_anomalies, offline_mode,
                    model_configured, thinking_level, output_dir,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'QUEUED', 'queued', ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    run_id,
                    ticker.upper().strip(),
                    company_name or ticker.upper().strip(),
                    cutoff_date,
                    max_anomalies,
                    1 if offline_mode else 0,
                    model_configured,
                    thinking_level,
                    output_dir,
                    now,
                    now
                )
            )
        self.add_event(
            run_id=run_id,
            stage="queued",
            message=f"Investigation for {ticker.upper()} registered and placed in execution queue.",
            severity="INFO"
        )
        return self.get_run(run_id)

    def update_run_status(
        self,
        run_id: str,
        status: str,
        current_stage: Optional[str] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        company_name: Optional[str] = None,
        model_used: Optional[str] = None,
        provider_used: Optional[str] = None,
        quarters_analyzed: Optional[int] = None,
        anomalies_detected_count: Optional[int] = None,
        no_material_anomaly: Optional[bool] = None,
        adjudication_verdict: Optional[str] = None,
        data_sufficiency: Optional[str] = None,
        evidence_strength: Optional[str] = None,
        primary_finding: Optional[str] = None,
        validation_passed: Optional[bool] = None,
        error_message: Optional[str] = None,
        error_trace: Optional[str] = None,
        pdf_path: Optional[str] = None,
        json_path: Optional[str] = None,
        chart_path: Optional[str] = None,
        manifest_path: Optional[str] = None,
        snapshot_path: Optional[str] = None
    ) -> None:
        """Dynamically updates fields for a run."""
        fields = ["status = ?", "updated_at = ?"]
        now = datetime.now(timezone.utc).isoformat()
        values: List[Any] = [status, now]

        def add_field(name: str, val: Any):
            if val is not None:
                fields.append(f"{name} = ?")
                values.append(val)

        add_field("current_stage", current_stage)
        add_field("started_at", started_at)
        add_field("completed_at", completed_at)
        add_field("duration_seconds", duration_seconds)
        add_field("company_name", company_name)
        add_field("model_used", model_used)
        add_field("provider_used", provider_used)
        add_field("quarters_analyzed", quarters_analyzed)
        add_field("anomalies_detected_count", anomalies_detected_count)
        if no_material_anomaly is not None:
            add_field("no_material_anomaly", 1 if no_material_anomaly else 0)
        add_field("adjudication_verdict", adjudication_verdict)
        add_field("data_sufficiency", data_sufficiency)
        add_field("evidence_strength", evidence_strength)
        add_field("primary_finding", primary_finding)
        if validation_passed is not None:
            add_field("validation_passed", 1 if validation_passed else 0)
        add_field("error_message", error_message)
        add_field("error_trace", error_trace)
        add_field("pdf_path", pdf_path)
        add_field("json_path", json_path)
        add_field("chart_path", chart_path)
        add_field("manifest_path", manifest_path)
        add_field("snapshot_path", snapshot_path)

        values.append(run_id)
        sql = f"UPDATE investigation_runs SET {', '.join(fields)} WHERE run_id = ?;"
        with self.get_connection() as conn:
            conn.execute(sql, values)

    def add_event(
        self,
        run_id: str,
        stage: str,
        message: str,
        severity: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Appends a real-time event to the run's audit trail."""
        now = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata, default=str) if metadata else None
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO run_events (run_id, timestamp, stage, severity, message, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (run_id, now, stage, severity.upper(), message, meta_str)
            )
            event_id = cursor.lastrowid
            # Also keep current_stage updated on run record
            conn.execute(
                "UPDATE investigation_runs SET current_stage = ?, updated_at = ? WHERE run_id = ?;",
                (stage, now, run_id)
            )
            return event_id

    def save_run_data(
        self,
        run_id: str,
        summary: Optional[Dict[str, Any]] = None,
        discovery: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        anomalies: Optional[List[Dict[str, Any]]] = None,
        hypotheses: Optional[List[Dict[str, Any]]] = None,
        adjudication: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
        observations: Optional[List[Dict[str, Any]]] = None,
        logs: Optional[List[str]] = None
    ) -> None:
        """Stores large structured analysis bundles."""
        s_json = json.dumps(summary, default=str) if summary else None
        d_json = json.dumps(discovery, default=str) if discovery else None
        m_json = json.dumps(metrics, default=str) if metrics else None
        a_json = json.dumps(anomalies, default=str) if anomalies else None
        h_json = json.dumps(hypotheses, default=str) if hypotheses else None
        adj_json = json.dumps(adjudication, default=str) if adjudication else None
        e_json = json.dumps(evidence, default=str) if evidence else None
        o_json = json.dumps(observations, default=str) if observations else None
        l_json = json.dumps(logs, default=str) if logs else None

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO run_data (
                    run_id, summary_json, discovery_json, metrics_json,
                    anomalies_json, hypotheses_json, adjudication_json,
                    evidence_json, observations_json, logs_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    summary_json = excluded.summary_json,
                    discovery_json = excluded.discovery_json,
                    metrics_json = excluded.metrics_json,
                    anomalies_json = excluded.anomalies_json,
                    hypotheses_json = excluded.hypotheses_json,
                    adjudication_json = excluded.adjudication_json,
                    evidence_json = excluded.evidence_json,
                    observations_json = excluded.observations_json,
                    logs_json = excluded.logs_json;
                """,
                (run_id, s_json, d_json, m_json, a_json, h_json, adj_json, e_json, o_json, l_json)
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single run summary record by run_id."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM investigation_runs WHERE run_id = ?;", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["offline_mode"] = bool(d.get("offline_mode"))
            d["no_material_anomaly"] = bool(d.get("no_material_anomaly"))
            d["validation_passed"] = bool(d.get("validation_passed"))
            return d

    def get_run_data(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves structured data payloads for a run."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM run_data WHERE run_id = ?;", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            res = {}
            for k in (
                "summary_json", "discovery_json", "metrics_json",
                "anomalies_json", "hypotheses_json", "adjudication_json",
                "evidence_json", "observations_json", "logs_json"
            ):
                val = row[k]
                clean_key = k.replace("_json", "")
                res[clean_key] = json.loads(val) if val else ({} if "json" in k and k != "logs_json" and k != "evidence_json" and k != "anomalies_json" and k != "hypotheses_json" and k != "observations_json" else [])
            return res

    def get_events(self, run_id: str, since_id: Optional[int] = None, limit: int = 250) -> List[Dict[str, Any]]:
        """Retrieves events for a run, optionally after since_id."""
        with self.get_connection() as conn:
            if since_id is not None:
                cursor = conn.execute(
                    """
                    SELECT * FROM run_events
                    WHERE run_id = ? AND id > ?
                    ORDER BY id ASC
                    LIMIT ?;
                    """,
                    (run_id, since_id, limit)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM run_events
                    WHERE run_id = ?
                    ORDER BY id ASC
                    LIMIT ?;
                    """,
                    (run_id, limit)
                )
            rows = cursor.fetchall()
            events = []
            for r in rows:
                ev = dict(r)
                if ev.get("metadata_json"):
                    try:
                        ev["metadata"] = json.loads(ev["metadata_json"])
                    except Exception:
                        ev["metadata"] = None
                else:
                    ev["metadata"] = None
                events.append(ev)
            return events

    def list_runs(
        self,
        page: int = 1,
        per_page: int = 20,
        ticker: Optional[str] = None,
        status: Optional[str] = None,
        verdict: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Lists runs with filtering and pagination."""
        page = max(1, page)
        per_page = max(1, min(100, per_page))
        offset = (page - 1) * per_page

        where_clauses = []
        params: List[Any] = []

        if ticker:
            where_clauses.append("ticker = ?")
            params.append(ticker.upper().strip())

        if status:
            where_clauses.append("status = ?")
            params.append(status.upper().strip())

        if verdict:
            where_clauses.append("adjudication_verdict = ?")
            params.append(verdict.upper().strip())

        if search:
            s = f"%{search.strip()}%"
            where_clauses.append("(ticker LIKE ? OR company_name LIKE ? OR primary_finding LIKE ?)")
            params.extend([s, s, s])

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        with self.get_connection() as conn:
            count_cursor = conn.execute(f"SELECT COUNT(*) FROM investigation_runs {where_sql};", params)
            total_count = count_cursor.fetchone()[0]

            query_sql = f"""
                SELECT * FROM investigation_runs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?;
            """
            cursor = conn.execute(query_sql, params + [per_page, offset])
            rows = cursor.fetchall()
            runs = []
            for r in rows:
                d = dict(r)
                d["offline_mode"] = bool(d.get("offline_mode"))
                d["no_material_anomaly"] = bool(d.get("no_material_anomaly"))
                d["validation_passed"] = bool(d.get("validation_passed"))
                runs.append(d)

            return runs, total_count

    def get_overview_metrics(self) -> Dict[str, Any]:
        """Calculates accurate aggregate research metrics strictly from persisted records."""
        with self.get_connection() as conn:
            # 1. Total counts by status
            cur = conn.execute("""
                SELECT 
                    COUNT(*) as total_runs,
                    SUM(CASE WHEN status = 'SUCCEEDED' THEN 1 ELSE 0 END) as total_completed,
                    SUM(CASE WHEN status IN ('RUNNING', 'QUEUED') THEN 1 ELSE 0 END) as total_active,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as total_failed,
                    SUM(CASE WHEN adjudication_verdict = 'SUPPORTED' AND no_material_anomaly = 0 THEN 1 ELSE 0 END) as total_attention,
                    SUM(CASE WHEN provider_used = 'ollama' THEN 1 ELSE 0 END) as total_fallback_used
                FROM investigation_runs;
            """)
            counts = dict(cur.fetchone())

            # 2. Most recent run
            cur = conn.execute("""
                SELECT run_id, ticker, company_name, adjudication_verdict, status, created_at, cutoff_date
                FROM investigation_runs
                ORDER BY created_at DESC
                LIMIT 1;
            """)
            latest_row = cur.fetchone()
            latest_run = dict(latest_row) if latest_row else None

            # 3. Most recently analyzed distinct company
            cur = conn.execute("""
                SELECT ticker, company_name, MAX(created_at) as last_seen
                FROM investigation_runs
                GROUP BY ticker, company_name
                ORDER BY last_seen DESC
                LIMIT 1;
            """)
            recent_company_row = cur.fetchone()
            recent_company = dict(recent_company_row) if recent_company_row else None

            # 4. Fallback frequency
            completed_runs = counts.get("total_completed") or 0
            fallback_runs = counts.get("total_fallback_used") or 0
            fallback_pct = round((fallback_runs / completed_runs * 100.0), 1) if completed_runs > 0 else 0.0

            return {
                "total_completed": completed_runs,
                "total_active": counts.get("total_active") or 0,
                "total_attention": counts.get("total_attention") or 0,
                "total_failed": counts.get("total_failed") or 0,
                "latest_run": latest_run,
                "most_recent_company": recent_company.get("company_name", recent_company.get("ticker")) if recent_company else None,
                "most_recent_ticker": recent_company.get("ticker") if recent_company else None,
                "fallback_count": fallback_runs,
                "fallback_pct": fallback_pct,
                "latest_cutoff": latest_run.get("cutoff_date") if latest_run else None
            }


# Default singleton run store
run_store = RunStore()
