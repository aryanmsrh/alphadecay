import os
import re
from typing import Dict, Any, List, Optional
import httpx
from bs4 import BeautifulSoup


class ScreenerScraper:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    def fetch_company_data(self, ticker: str) -> Dict[str, Any]:
        clean_ticker = ticker.upper().strip()
        urls = [
            f"https://www.screener.in/company/{clean_ticker}/consolidated/",
            f"https://www.screener.in/company/{clean_ticker}/"
        ]

        html_text = ""
        final_url = ""
        with httpx.Client(headers=self.HEADERS, timeout=self.timeout, follow_redirects=True) as client:
            for url in urls:
                try:
                    res = client.get(url)
                    if res.status_code == 200 and len(res.text) > 1000:
                        html_text = res.text
                        final_url = str(res.url)
                        break
                except Exception:
                    continue

        if not html_text:
            raise RuntimeError(f"Could not retrieve financial data for ticker '{clean_ticker}' from Screener.in")

        return self._parse_html(html_text, clean_ticker, final_url)

    def _parse_table(self, soup: BeautifulSoup, section_id: str) -> Dict[str, Any]:
        section = soup.find("section", id=section_id)
        if not section:
            return {"periods": [], "rows": {}}

        table = section.find("table")
        if not table:
            return {"periods": [], "rows": {}}

        headers = []
        thead = table.find("thead")
        if thead:
            for th in thead.find_all("th"):
                text = th.get_text(strip=True)
                if text:
                    headers.append(text)

        rows = {}
        tbody = table.find("tbody")
        if tbody:
            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if not tds:
                    continue
                row_label = tds[0].get_text(strip=True).replace("+", "").strip()
                values = []
                for td in tds[1:]:
                    raw_val = td.get_text(strip=True).replace(",", "").replace("%", "")
                    try:
                        values.append(float(raw_val))
                    except ValueError:
                        values.append(raw_val)
                rows[row_label] = values

        return {"periods": headers, "rows": rows}

    def _parse_html(self, html: str, ticker: str, source_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        company_name = ticker
        name_tag = soup.find("h1")
        if name_tag:
            company_name = name_tag.get_text(strip=True)

        quarters = self._parse_table(soup, "quarters")
        profit_loss = self._parse_table(soup, "profit-loss")
        balance_sheet = self._parse_table(soup, "balance-sheet")
        cash_flow = self._parse_table(soup, "cash-flow")
        ratios_table = self._parse_table(soup, "ratios")

        concall_transcripts = []
        docs_section = soup.find("section", id="documents")
        if docs_section:
            for a in docs_section.find_all("a"):
                text = a.get_text(strip=True)
                href = a.get("href", "")
                if "transcript" in text.lower() or "transcript" in href.lower():
                    if href.startswith("/"):
                        href = f"https://www.screener.in{href}"
                    concall_transcripts.append({"title": text, "url": href})

        return {
            "ticker": ticker,
            "company_name": company_name,
            "source_url": source_url,
            "quarters": quarters,
            "profit_loss": profit_loss,
            "balance_sheet": balance_sheet,
            "cash_flow": cash_flow,
            "ratios_table": ratios_table,
            "concall_transcripts": concall_transcripts
        }
