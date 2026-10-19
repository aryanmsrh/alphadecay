import re
import os
import json
import time
from urllib.parse import urljoin
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent


class ScreenerIngestionError(RuntimeError):
    """Raised when statutory data ingestion from Screener.in fails or returns malformed HTML."""
    pass


class ScreenerScraper:
    """
    Deterministic scraper for Screener.in financial tables using httpx + BeautifulSoup4.
    Extracts quarterly results, annual P&L, balance sheets, cash flows, historical ratios,
    and concall transcripts with column-alignment preservation and typed missingness.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self, use_cache: bool = False, cache_ttl_seconds: int = 86400):
        self.use_cache = use_cache
        self.cache_ttl = cache_ttl_seconds
        self.cache_dir = BASE_DIR / "data" / "cache"

    def _get_cache_path(self, ticker: str) -> Path:
        return self.cache_dir / f"screener_{ticker.upper()}.json"

    def _read_cache(self, ticker: str) -> Optional[Dict[str, Any]]:
        if not self.use_cache:
            return None
        cache_file = self._get_cache_path(ticker)
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_at = data.get("_cached_at_epoch", 0)
            if time.time() - cached_at > self.cache_ttl:
                return None  # Cache expired
            return data
        except Exception:
            return None

    def _write_cache(self, ticker: str, data: Dict[str, Any]):
        if not self.use_cache:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self._get_cache_path(ticker)
            to_save = dict(data)
            to_save["_cached_at_epoch"] = time.time()
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=2, default=str)
        except Exception:
            pass

    @staticmethod
    def _parse_cell_value(val_str: str) -> Optional[float]:
        """
        Parses numeric cells cleanly:
        - Commas, percentage signs, currency symbols stripped.
        - Parenthesized negative numbers e.g. '(123)' -> -123.0
        - Explicit missing markers ('', '-', '–', '—', 'nan', 'N/A') -> None
        """
        if not val_str:
            return None
        s = val_str.strip().replace(",", "").replace("%", "").replace("₹", "").replace("$", "")
        if s in ("", "-", "–", "—", "nan", "None", "N/A", "null"):
            return None

        # Check parenthesized negative e.g. (150.5)
        m_neg = re.match(r"^\(([\d\.]+)\)$", s)
        if m_neg:
            try:
                return -float(m_neg.group(1))
            except ValueError:
                return None

        try:
            return float(s)
        except ValueError:
            return None

    def fetch_company_data(self, ticker: str) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        if not ticker:
            raise ScreenerIngestionError("Empty ticker symbol provided.")

        cached = self._read_cache(ticker)
        if cached:
            print(f"[Screener Ingestion] Using cached disclosures for '{ticker}'.")
            return cached

        urls_to_try = [
            f"https://www.screener.in/company/{ticker}/consolidated/",
            f"https://www.screener.in/company/{ticker}/",
        ]

        html_content = ""
        final_url = ""
        last_error = None

        with httpx.Client(headers=self.HEADERS, timeout=20.0, follow_redirects=True) as client:
            for url in urls_to_try:
                try:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        # Validate that it's an actual company page, not a login wall or captcha
                        if "Sign in" in resp.text and "Daily search limit reached" in resp.text:
                            raise ScreenerIngestionError("Screener.in rate limit / login wall encountered.")
                        if "Company not found" in resp.text:
                            continue
                        html_content = resp.text
                        final_url = str(resp.url)
                        break
                    elif resp.status_code == 404:
                        continue
                    else:
                        last_error = f"HTTP {resp.status_code}"
                except Exception as e:
                    last_error = str(e)
                    continue

        if not html_content:
            raise ScreenerIngestionError(
                f"Failed to fetch live statutory data for ticker '{ticker}' from Screener.in. Error: {last_error}"
            )

        parsed_data = self._parse_screener_html(html_content, ticker, final_url)
        self._write_cache(ticker, parsed_data)
        return parsed_data

    def _parse_table(self, soup: BeautifulSoup, section_id: str) -> Dict[str, Any]:
        """
        Parses a Screener statutory table, preserving column alignments and missing values.
        """
        section = soup.find("section", id=section_id)
        if not section:
            return {"periods": [], "rows": {}}

        table = section.find("table")
        if not table:
            return {"periods": [], "rows": {}}

        # Parse headers from thead
        headers = []
        thead = table.find("thead")
        if thead:
            th_tags = thead.find_all("th")
            for th in th_tags:
                text = th.get_text(strip=True)
                if text:
                    headers.append(text)

        # In Screener tables, the first column header might be empty or a label like 'Report Date'
        # Period columns are the remainder
        period_headers = headers

        rows: Dict[str, List[Optional[float]]] = {}
        tbody = table.find("tbody")
        if tbody:
            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if not tds:
                    continue
                raw_label = tds[0].get_text(strip=True).replace("+", "").strip()
                # Clean label
                row_label = raw_label

                clean_values = []
                for td in tds[1:]:
                    val_str = td.get_text(strip=True)
                    clean_values.append(self._parse_cell_value(val_str))

                # Handle duplicate row labels by disambiguating if necessary
                if row_label in rows:
                    row_label = f"{row_label} (Duplicate)"
                rows[row_label] = clean_values

        return {"periods": period_headers, "rows": rows}

    def _parse_screener_html(self, html: str, ticker: str, final_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        # Validate company presence
        name_tag = soup.find("h1")
        if not name_tag:
            raise ScreenerIngestionError(f"Could not locate company header in response for ticker '{ticker}'.")

        company_name = name_tag.get_text(strip=True)

        # Top Widget Key Ratios
        ratios = {}
        ratio_items = soup.find_all("li", class_="flex")
        for item in ratio_items:
            name = item.find("span", class_="name")
            value = item.find("span", class_="nowrap")
            if name and value:
                ratios[name.get_text(strip=True)] = value.get_text(strip=True)

        # Parse Statutory Tables
        quarters_data = self._parse_table(soup, "quarters")
        profit_loss_data = self._parse_table(soup, "profit-loss")
        balance_sheet_data = self._parse_table(soup, "balance-sheet")
        cash_flow_data = self._parse_table(soup, "cash-flow")
        ratios_table = self._parse_table(soup, "ratios")

        # Concall Transcripts in Documents Section (resolve relative URLs)
        concall_transcripts = []
        docs_section = soup.find("section", id="documents")
        if docs_section:
            for a in docs_section.find_all("a"):
                text = a.get_text(strip=True)
                href = a.get("href", "")
                if "transcript" in text.lower() or "transcript" in href.lower():
                    resolved_url = urljoin(final_url or "https://www.screener.in", href)
                    concall_transcripts.append({
                        "title": text,
                        "url": resolved_url
                    })

        # Basic integrity check: at least quarters table must have periods
        if not quarters_data.get("periods") and not profit_loss_data.get("periods"):
            raise ScreenerIngestionError(f"Zero financial periods extracted from Screener page for '{ticker}'.")

        return {
            "ticker": ticker,
            "company_name": company_name,
            "source_url": final_url,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "data_source_type": "screener_aggregator",
            "ratios": ratios,
            "quarters": quarters_data,
            "profit_loss": profit_loss_data,
            "balance_sheet": balance_sheet_data,
            "cash_flow": cash_flow_data,
            "ratios_table": ratios_table,
            "concall_transcripts": concall_transcripts,
        }
