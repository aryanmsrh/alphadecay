import re
import io
import httpx
import pypdf
from typing import List, Dict, Any, Optional

class ConcallHarvester:
    """
    Direct Earnings Concall Transcript PDF Extraction & Analyst Q&A Grilling (Feature B).
    Parses statutory BSE/NSE transcript PDFs to isolate analyst cross-examination
    on distributor credit, quick commerce discounts, working capital stretch, and volume growth.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*",
    }

    FORENSIC_KEYWORDS = [
        "distributor", "credit", "receivable", "debtor", "inventory",
        "working capital", "quick commerce", "blinkit", "zepto", "instamart",
        "volume growth", "underlying volume", "uvg", "channel", "rebate", "pricing"
    ]

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    def harvest_transcript(self, pdf_url: str, max_excerpts: int = 3) -> List[Dict[str, Any]]:
        """
        Downloads BSE transcript PDF, locates Q&A section, and extracts analyst grilling excerpts.
        """
        if not pdf_url:
            return []

        resolved_pdf_url = pdf_url
        try:
            with httpx.Client(headers=self.HEADERS, timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(pdf_url)
                if resp.status_code != 200 or len(resp.content) < 5000:
                    return []
                # Ensure the payload is genuinely a PDF document
                if not resp.content.startswith(b"%PDF"):
                    return []
                resolved_pdf_url = str(resp.url)
                pdf_bytes = io.BytesIO(resp.content)
        except Exception:
            return []

        try:
            reader = pypdf.PdfReader(pdf_bytes)
            num_pages = len(reader.pages)
            if num_pages == 0:
                return []

            pages_text = []
            for page_idx in range(num_pages):
                txt = reader.pages[page_idx].extract_text() or ""
                pages_text.append(txt)

            full_doc = "\n".join(pages_text)
            
            # Locate start of Q&A section
            qa_start_idx = -1
            qa_markers = [
                "question-and-answer session",
                "question and answer session",
                "questions and answers",
                "q&a session",
                "question & answer"
            ]
            lower_doc = full_doc.lower()
            for marker in qa_markers:
                pos = lower_doc.find(marker)
                if pos != -1:
                    qa_start_idx = pos
                    break

            qa_text = full_doc[qa_start_idx:] if qa_start_idx != -1 else full_doc

            # Split into speaker turns / dialogue blocks
            paragraphs = re.split(r"\n(?=[A-Z][a-zA-Z\s\.\(\)]+:\s*)", qa_text)

            matches: List[Dict[str, Any]] = []
            for i, p in enumerate(paragraphs):
                p_clean = " ".join(p.split())
                p_lower = p_clean.lower()

                matched_kw = [kw for kw in self.FORENSIC_KEYWORDS if kw in p_lower]
                if matched_kw and len(p_clean) > 80:
                    context = p_clean
                    if i + 1 < len(paragraphs):
                        next_turn = " ".join(paragraphs[i + 1].split())
                        context += "\n[Management Response]: " + next_turn

                    matches.append({
                        "matched_keywords": matched_kw,
                        "excerpt": context,
                        "source_url": resolved_pdf_url
                    })

                    if len(matches) >= max_excerpts:
                        break

            return matches

        except Exception:
            return []

if __name__ == "__main__":
    harvester = ConcallHarvester()
    test_url = "https://www.bseindia.com/stockinfo/AnnPdfOpen.aspx?Pname=f8bf7fdd-0f7d-4440-a443-08ea9a8e6d04.pdf"
    results = harvester.harvest_transcript(test_url, max_excerpts=2)
    print(f"Extracted {len(results)} forensic concall excerpts")
    for r in results:
        print(f"Keywords: {r['matched_keywords']}")
        print(f"Excerpt:\n{r['excerpt']}")
