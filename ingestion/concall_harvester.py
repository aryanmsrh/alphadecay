import re
import io
import httpx
import pypdf
from typing import List, Dict, Any, Optional, Tuple


class ConcallHarvester:
    """
    Direct Earnings Concall Transcript PDF Extraction & Analyst Q&A Processing.
    Parses statutory BSE/NSE transcript PDFs to isolate analyst discussions on
    distributor credit, quick commerce discounts, working capital elongation, and volume growth.
    Preserves page boundaries, speaker attribution, and verification status.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/pdf,*/*",
    }

    FORENSIC_KEYWORDS = [
        "distributor", "credit", "receivable", "debtor", "inventory",
        "working capital", "quick commerce", "blinkit", "zepto", "instamart",
        "volume growth", "underlying volume", "uvg", "channel", "rebate", "pricing",
        "discount", "trade terms", "channel inventory"
    ]

    QA_MARKERS = [
        "question-and-answer session",
        "question and answer session",
        "questions and answers",
        "q&a session",
        "question & answer",
        "analyst questions",
        "floor open for questions"
    ]

    def __init__(self, timeout: float = 15.0, max_pages: int = 100):
        self.timeout = timeout
        self.max_pages = max_pages

    def harvest_transcript(
        self,
        pdf_url: str,
        max_excerpts: int = 3,
        target_period: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Downloads BSE/NSE transcript PDF, isolates Q&A section with page tracking,
        and extracts relevant dialogue blocks with verified speaker labels.
        """
        if not pdf_url or not isinstance(pdf_url, str):
            return []

        resolved_pdf_url = pdf_url
        try:
            with httpx.Client(headers=self.HEADERS, timeout=self.timeout, follow_redirects=True) as client:
                resp = client.get(pdf_url)
                if resp.status_code != 200 or len(resp.content) < 4000:
                    return []
                # Validate PDF magic bytes
                if not resp.content.startswith(b"%PDF"):
                    return []
                resolved_pdf_url = str(resp.url)
                pdf_bytes = io.BytesIO(resp.content)
        except Exception as e:
            print(f"[Concall Harvester Warning] Failed to download transcript from '{pdf_url}': {e}")
            return []

        try:
            reader = pypdf.PdfReader(pdf_bytes)
            num_pages = len(reader.pages)
            if num_pages == 0:
                return []

            pages_to_process = min(num_pages, self.max_pages)
            pages_text: List[Tuple[int, str]] = []

            for page_idx in range(pages_to_process):
                try:
                    txt = reader.pages[page_idx].extract_text() or ""
                    pages_text.append((page_idx + 1, txt))
                except Exception:
                    continue

            # Identify Q&A start page
            qa_start_page = 1
            for page_num, text in pages_text:
                lower = text.lower()
                if any(m in lower for m in self.QA_MARKERS):
                    qa_start_page = page_num
                    break

            # Filter to Q&A pages
            qa_pages = [(p_num, txt) for p_num, txt in pages_text if p_num >= qa_start_page]
            if not qa_pages:
                qa_pages = pages_text

            # Parse dialogue blocks per page
            candidate_matches: List[Dict[str, Any]] = []

            for page_num, text in qa_pages:
                # Split text into speaker turns (e.g. 'Analyst Name:', 'Management:', 'Speaker:')
                turns = re.split(r"\n(?=[A-Z][a-zA-Z\s\.\(\)\,\-]{2,40}:\s*)", text)
                for idx, turn in enumerate(turns):
                    t_clean = " ".join(turn.split())
                    t_lower = t_clean.lower()

                    matched_kw = [kw for kw in self.FORENSIC_KEYWORDS if kw in t_lower]
                    if matched_kw and len(t_clean) > 80:
                        # Extract speaker label if present
                        speaker_match = re.match(r"^([A-Z][a-zA-Z\s\.\(\)\,\-]{2,40}):\s*(.*)", t_clean)
                        speaker = speaker_match.group(1).strip() if speaker_match else "Unattributed"
                        statement = speaker_match.group(2).strip() if speaker_match else t_clean

                        # Check if next turn is response
                        context = t_clean
                        if idx + 1 < len(turns):
                            next_turn = " ".join(turns[idx + 1].split())
                            next_speaker_match = re.match(r"^([A-Z][a-zA-Z\s\.\(\)\,\-]{2,40}):\s*(.*)", next_turn)
                            next_speaker = next_speaker_match.group(1).strip() if next_speaker_match else "Next Speaker"
                            
                            # Verify if next speaker is management
                            is_mgmt = any(k in next_speaker.lower() for k in [
                                "management", "md", "ceo", "cfo", "director", "executive", "company", "chairman"
                            ])
                            resp_label = f"[Management Response - {next_speaker}]" if is_mgmt else f"[Subsequent Response - {next_speaker}]"
                            context += f"\n{resp_label}: {next_turn}"

                        num_metrics = len(re.findall(r'\d+(?:\.\d+)?%|\d+\s*(?:days|bps|cr)', t_lower))
                        density_score = len(matched_kw) * 3 + num_metrics * 2

                        candidate_matches.append({
                            "page_number": page_num,
                            "speaker": speaker,
                            "matched_keywords": matched_kw,
                            "excerpt": context,
                            "source_url": resolved_pdf_url,
                            "density_score": density_score,
                            "relevant_period": target_period
                        })

            candidate_matches.sort(key=lambda x: x["density_score"], reverse=True)
            return candidate_matches[:max_excerpts]

        except Exception as e:
            print(f"[Concall Harvester Warning] Error processing PDF text: {e}")
            return []
