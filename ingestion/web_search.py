import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import httpx
from config import TAVILY_API_KEY, USE_OFFLINE_MODE

class TavilySearchClient:
    """
    Search client for AI agents using Tavily API.
    Returns clean markdown excerpts and source URLs.
    Includes an automatic offline/mock fallback for testing without credentials.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or TAVILY_API_KEY
        self.offline = USE_OFFLINE_MODE or not bool(self.api_key)

    def search(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Executes a targeted search query. Returns list of {title, url, content}.
        """
        if self.offline:
            return self._mock_fallback_search(query)

        try:
            # Using direct HTTP request to Tavily endpoint for minimal overhead & maximum reliability
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": "advanced",
                "include_answer": True,
                "max_results": max_results
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    results = []
                    for item in data.get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "content": item.get("content", ""),
                            "score": item.get("score", 1.0)
                        })
                    return results
                else:
                    print(f"[Tavily Warning] API returned status {res.status_code}. Using fallback.")
                    return self._mock_fallback_search(query)
        except Exception as e:
            print(f"[Tavily Error] {e}. Falling back to offline search.")
            return self._mock_fallback_search(query)

    def _mock_fallback_search(self, query: str) -> List[Dict[str, Any]]:
        """
        Graceful offline/test fallback so pipeline execution never crashes without internet/API keys.
        """
        return [
            {
                "title": f"Regulatory & Concall Search: {query[:50]}",
                "url": "https://www.bseindia.com/corporates/ann.html",
                "content": f"[Offline Mock Search Result] Simulated finding for query: '{query}'. Management cited festive demand shifts, raw material fluctuations, and distributor channel discussions in audited notes.",
                "score": 0.85
            }
        ]

if __name__ == "__main__":
    client = TavilySearchClient()
    print("Testing TavilySearchClient...")
    res = client.search("HUL Q3 FY24 distributor receivable days concall", max_results=2)
    print(f"Results returned: {len(res)}")
    print(f"Sample: {res[0]['title']} -> {res[0]['url']}")
