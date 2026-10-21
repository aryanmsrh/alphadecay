import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


class InvestigationArchive:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or "data/runs")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _run_dir(self, run_id: str) -> Path:
        p = self.data_dir / run_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save_report(self, report_data: Dict[str, Any]) -> None:
        run_id = report_data["run_id"]
        run_folder = self._run_dir(run_id)
        path = run_folder / "run.json"
        temp_path = run_folder / "run.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        temp_path.replace(path)

    def get_report(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self.data_dir / run_id / "run.json"
        if not path.exists():
            legacy_path = self.data_dir / f"{run_id}.json"
            if legacy_path.exists():
                path = legacy_path
            else:
                return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def update_status(self, run_id: str, status: str, error: Optional[str] = None) -> Optional[Dict[str, Any]]:
        data = self.get_report(run_id)
        if not data:
            return None
        data["status"] = status
        if error:
            data["error"] = error
        if status in ("COMPLETED", "FAILED"):
            data["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.save_report(data)
        return data

    def list_reports(self, limit: int = 50) -> List[Dict[str, Any]]:
        reports = []
        seen_ids = set()

        for folder in self.data_dir.iterdir():
            if folder.is_dir():
                report_file = folder / "run.json"
                if report_file.exists():
                    try:
                        with open(report_file, "r", encoding="utf-8") as f:
                            d = json.load(f)
                            rid = d.get("run_id") or folder.name
                            seen_ids.add(rid)
                            reports.append(d)
                    except Exception:
                        continue

        for file in self.data_dir.glob("*.json"):
            rid = file.stem
            if rid not in seen_ids:
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        reports.append(d)
                        seen_ids.add(rid)
                except Exception:
                    continue

        reports.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return reports[:limit]

    def delete_report(self, run_id: str) -> bool:
        folder = self.data_dir / run_id
        deleted = False
        if folder.exists() and folder.is_dir():
            shutil.rmtree(folder)
            deleted = True
        legacy_file = self.data_dir / f"{run_id}.json"
        if legacy_file.exists():
            legacy_file.unlink()
            deleted = True
        return deleted

    def get_metrics(self) -> Dict[str, Any]:
        all_reports = self.list_reports(limit=500)
        total = len(all_reports)
        completed_reports = [r for r in all_reports if r.get("status") == "COMPLETED"]
        completed = len(completed_reports)
        active = sum(1 for r in all_reports if r.get("status") in ("QUEUED", "RUNNING"))

        latest = all_reports[0] if all_reports else None
        latest_company = (
            latest.get("company_name") or latest.get("ticker")
            if latest
            else None
        )
        latest_ticker = latest.get("ticker") if latest else None

        return {
            "total_runs": total,
            "total_completed": completed,
            "total_active": active,
            "most_recent_company": latest_company,
            "latest_ticker": latest_ticker,
        }

    save_run = save_report
    get_run = get_report
    list_runs = list_reports
    delete_run = delete_report


archive = InvestigationArchive()
