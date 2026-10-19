from typing import List, Dict, Any, Optional
import httpx
from config import TAVILY_API_KEY, USE_OFFLINE_MODE


class TavilySearchClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or TAVILY_API_KEY
        self.offline = USE_OFFLINE_MODE or not bool(self.api_key)

    def search(self, query: str, max_results: int = 2) -> List[Dict[str, Any]]:
        if self.offline:
            return []

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    hits = res.json().get("results", [])
                    return [
                        {
                            "title": h.get("title", ""),
                            "url": h.get("url", ""),
                            "content": h.get("content", "")[:400]
                        }
                        for h in hits
                    ]
        except Exception:
            pass

        return []
