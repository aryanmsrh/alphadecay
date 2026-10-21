from typing import Any, Dict, List, Optional
import httpx
from config import TAVILY_API_KEY


class TavilySearchClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or TAVILY_API_KEY
        self.offline = not bool(self.api_key)

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        if self.offline:
            return []

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": f"{query} India NSE BSE -sec.gov -stock -share -price -quote",
            "search_depth": "advanced",
            "max_results": max_results,
            "exclude_domains": [
                "sec.gov",
                "edgar",
                "nyse.com",
                "nasdaq.com",
                "macrotrends.net",
                "wsj.com",
                "investing.com",
                "in.investing.com",
                "finance.yahoo.com",
                "tradingview.com",
                "moneycontrol.com",
                "youtube.com",
                "groww.in",
                "upstox.com",
                "angelone.in",
                "5paisa.com",
            ],
        }

        try:
            with httpx.Client(timeout=12.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    hits = res.json().get("results", [])
                    clean_hits = []
                    for h in hits:
                        url_low = (h.get("url", "") or "").lower()
                        if "sec.gov" in url_low or "edgar" in url_low:
                            continue
                        if h.get("content"):
                            clean_hits.append({
                                "title": h.get("title", ""),
                                "url": h.get("url", ""),
                                "content": h.get("content", "")[:600],
                            })
                    return clean_hits
        except Exception:
            pass

        return []
