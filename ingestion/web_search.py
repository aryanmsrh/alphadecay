import sys
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import httpx
from config import TAVILY_API_KEY, USE_OFFLINE_MODE

logger = logging.getLogger("alphadecay.search")


class TavilySearchClient:
    """
    Search client for forensic evidence retrieval using Tavily Search API.
    Provides targeted queries, domain filtering, and sanitized logging.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or TAVILY_API_KEY
        self.offline = USE_OFFLINE_MODE or not bool(self.api_key)

    def search(
        self,
        query: str,
        max_results: int = 3,
        search_depth: str = "advanced"
    ) -> List[Dict[str, Any]]:
        """
        Executes a targeted search query with sanitized logging and error resilience.
        """
        if self.offline:
            print(f"\n[Search Notice] Offline mode active or missing TAVILY_API_KEY. Skipping live web search.")
            return []

        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "include_answer": True,
            "max_results": max_results,
            "exclude_domains": [
                "investing.com", "finance.yahoo.com", "tradingview.com",
                "moneycontrol.com", "groww.in", "upstox.com", "angelone.in", "5paisa.com",
                "youtube.com", "instagram.com", "facebook.com", "tiktok.com"
            ]
        }

        print("\n" + "=" * 70)
        print(f"[HTTP API REQUEST -> Tavily Search Engine]")
        print(f"  • Endpoint:    {url}")
        print(f"  • Query:       '{query}'")
        print(f"  • Search Depth: {search_depth} | Max Results: {max_results}")
        print("=" * 70)

        t0 = time.time()
        try:
            with httpx.Client(timeout=20.0) as client:
                res = client.post(url, json=payload)
                elapsed = round(time.time() - t0, 2)
                if res.status_code == 200:
                    data = res.json()
                    raw_results = data.get("results", [])
                    print("\n" + "=" * 70)
                    print(f"[HTTP API RESPONSE <- Tavily Search Engine ({elapsed}s | Status: 200)]")
                    print(f"  • Total Hits Returned: {len(raw_results)}")
                    results = []
                    for idx, item in enumerate(raw_results, 1):
                        title = item.get("title", "")
                        source_url = item.get("url", "")
                        content = item.get("content", "")
                        score = item.get("score", 1.0)
                        print(f"\n  [Hit #{idx}] {title}")
                        print(f"      URL: {source_url}")
                        print(f"      Snippet: {content[:180].strip()}...")
                        results.append({
                            "title": title,
                            "url": source_url,
                            "content": content,
                            "score": score
                        })
                    print("=" * 70)
                    return results
                else:
                    print(f"\n[Tavily Search Warning] API returned status {res.status_code}: {res.text[:200]}")
                    return []
        except Exception as e:
            print(f"\n[Tavily Search Exception after {round(time.time() - t0, 2)}s] {e}")
            return []
