import re
import io
import httpx
import pypdf
from typing import List, Dict, Any


class ConcallHarvester:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*",
    }

    KEYWORDS = [
        "distributor", "credit", "receivable", "debtor", "inventory",
        "working capital", "quick commerce", "blinkit", "zepto", "channel",
        "volume growth", "pricing", "discount", "rebate"
    ]

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    def harvest_transcript(self, pdf_url: str, max_excerpts: int = 2) -> List[Dict[str, Any]]:
        if not pdf_url:
            return []

        try:
            with httpx.Client(headers=self.HEADERS, timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(pdf_url)
                if resp.status_code != 200 or len(resp.content) < 4000 or not resp.content.startswith(b"%PDF"):
                    return []
                pdf_bytes = io.BytesIO(resp.content)
                final_url = str(resp.url)
        except Exception:
            return []

        try:
            reader = pypdf.PdfReader(pdf_bytes)
            pages_text = []
            for i in range(min(40, len(reader.pages))):
                text = reader.pages[i].extract_text() or ""
                pages_text.append(text)

            full_doc = "\n".join(pages_text)
            paragraphs = re.split(r"\n(?=[A-Z][a-zA-Z\s\.\(\)]+:\s*)", full_doc)

            matches = []
            for p in paragraphs:
                p_clean = " ".join(p.split())
                p_lower = p_clean.lower()
                matched = [kw for kw in self.KEYWORDS if kw in p_lower]
                if matched and len(p_clean) > 80:
                    matches.append({
                        "source_url": final_url,
                        "matched_keywords": matched,
                        "excerpt": p_clean[:500]
                    })
                    if len(matches) >= max_excerpts:
                        break

            return matches
        except Exception:
            return []
