import io
import re
from typing import Any, Dict, List
import httpx
import pypdf


class ConcallHarvester:
  HEADERS = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      ),
      "Accept": "application/pdf,*/*",
  }

  KEYWORDS = [
      "distributor",
      "credit",
      "receivable",
      "debtor",
      "inventory",
      "working capital",
      "quick commerce",
      "modern trade",
      "channel",
      "volume growth",
      "uvg",
      "pricing",
      "margin",
      "ebitda",
      "cash flow",
      "payable",
      "demand",
      "rural",
      "urban",
      "store",
      "sssg",
      "inflation",
      "mix",
      "capex",
      "guidance",
      "supply chain",
  ]

  def __init__(self, timeout: float = 45.0):
    self.timeout = timeout

  def harvest_transcript(
      self, pdf_url: str, max_excerpts: int = 3
  ) -> List[Dict[str, Any]]:
    if not pdf_url:
      return []

    try:
      with httpx.Client(
          headers=self.HEADERS, timeout=self.timeout, follow_redirects=True
      ) as client:
        resp = client.get(pdf_url)
        if resp.status_code != 200:
          raise RuntimeError(f"Failed to download concall PDF (HTTP {resp.status_code}) from {pdf_url}")
        if len(resp.content) < 4000 or not resp.content.startswith(b"%PDF"):
          raise RuntimeError(f"Invalid PDF bytes received from {pdf_url}")
        pdf_bytes = io.BytesIO(resp.content)
        final_url = str(resp.url)
    except Exception as e:
      raise RuntimeError(f"Failed to harvest concall PDF from {pdf_url}: {e}")

    try:
      reader = pypdf.PdfReader(pdf_bytes)
      pages_text = []
      for i in range(min(45, len(reader.pages))):
        text = reader.pages[i].extract_text() or ""
        pages_text.append(text)

      full_doc = "\n".join(pages_text)
      paragraphs = re.split(r"\n(?=[A-Z][a-zA-Z\s\.\(\)]+:\s*)", full_doc)
      if len(paragraphs) < 5:
        paragraphs = [p.strip() for p in full_doc.split("\n\n") if p.strip()]

      scored_chunks = []
      for p in paragraphs:
        p_clean = " ".join(p.split())
        if len(p_clean) < 100:
          continue
        p_lower = p_clean.lower()
        matched = [kw for kw in self.KEYWORDS if kw in p_lower]
        has_numbers = bool(
            re.search(r"\b\d+(?:\.\d+)?(?:\s*%|\s*cr|\s*bps|\s*days)\b", p_lower)
        )
        score = len(matched) + (2 if has_numbers else 0)
        if score >= 2:
          scored_chunks.append((
              score,
              {
                  "source_url": final_url,
                  "matched_keywords": matched,
                  "excerpt": p_clean[:550],
              },
          ))

      scored_chunks.sort(key=lambda x: x[0], reverse=True)
      return [item[1] for item in scored_chunks[:max_excerpts]]
    except Exception as e:
      raise RuntimeError(f"Failed to parse concall PDF from {pdf_url}: {e}")