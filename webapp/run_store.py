import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


class RunStore:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir or "data/runs")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, run_id: str) -> Path:
        return self.data_dir / f"{run_id}.json"

    def save_run(self, run_data: Dict[str, Any]) -> None:
        run_id = run_data["run_id"]
        path = self._file_path(run_id)
        temp_path = self.data_dir / f"{run_id}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(run_data, f, indent=2)
        temp_path.replace(path)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self._file_path(run_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def update_status(self, run_id: str, status: str, error: Optional[str] = None) -> Optional[Dict[str, Any]]:
        data = self.get_run(run_id)
        if not data:
            return None
        data["status"] = status
        if error:
            data["error"] = error
        if status in ("COMPLETED", "FAILED"):
            data["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.save_run(data)
        return data

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        runs = []
        for file in self.data_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    runs.append(json.load(f))
            except Exception:
                continue
        runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return runs[:limit]

    def get_metrics(self) -> Dict[str, Any]:
        all_runs = self.list_runs(limit=500)
        total = len(all_runs)
        completed = sum(1 for r in all_runs if r.get("status") == "COMPLETED")
        active = sum(1 for r in all_runs if r.get("status") in ("QUEUED", "RUNNING"))
        attention = sum(1 for r in all_runs if r.get("verdict") == "SUPPORTED")
        fallback = sum(1 for r in all_runs if r.get("provider") == "ollama")

        latest_company = all_runs[0].get("company_name") or all_runs[0].get("ticker") if all_runs else None

        return {
            "total_runs": total,
            "total_completed": completed,
            "total_active": active,
            "total_attention": attention,
            "fallback_count": fallback,
            "fallback_pct": round((fallback / completed * 100), 1) if completed > 0 else 0.0,
            "most_recent_company": latest_company
        }


run_store = RunStore()
