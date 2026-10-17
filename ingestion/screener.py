import json
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class ScreenerScraper:
    """
    Ultra-fast, deterministic scraper for Screener.in statutory tables using httpx + BeautifulSoup4.
    Extracts trailing 8+ quarters of P&L, balance sheets, and operating cash flows.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache

    def _get_cache_path(self, ticker: str) -> Path:
        return CACHE_DIR / f"{ticker.upper()}_financials.json"

    def fetch_company_data(self, ticker: str) -> Dict[str, Any]:
        ticker = ticker.upper().strip()
        cache_file = self._get_cache_path(ticker)

        if self.use_cache and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass  # Fallback to fresh fetch if cache is corrupted

        urls_to_try = [
            f"https://www.screener.in/company/{ticker}/consolidated/",
            f"https://www.screener.in/company/{ticker}/",
        ]

        html_content = ""
        final_url = ""
        with httpx.Client(headers=self.HEADERS, timeout=12.0, follow_redirects=True) as client:
            for url in urls_to_try:
                try:
                    resp = client.get(url)
                    if resp.status_code == 200:
                        html_content = resp.text
                        final_url = url
                        break
                except Exception as e:
                    continue

        if not html_content:
            raise RuntimeError(f"Failed to fetch data for ticker '{ticker}' from Screener.in")

        parsed_data = self._parse_screener_html(html_content, ticker)
        parsed_data["source_url"] = final_url

        # Save to disk cache
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(parsed_data, f, indent=2)

        return parsed_data

    def _parse_table(self, soup: BeautifulSoup, section_id: str) -> Dict[str, Any]:
        section = soup.find("section", id=section_id)
        if not section:
            return {}

        table = section.find("table")
        if not table:
            return {}

        # Parse headers (quarters / years)
        headers = []
        thead = table.find("thead")
        if thead:
            for th in thead.find_all("th"):
                text = th.get_text(strip=True)
                if text:
                    headers.append(text)

        # Parse rows
        rows = {}
        tbody = table.find("tbody")
        if tbody:
            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if not tds:
                    continue
                row_label = tds[0].get_text(strip=True).replace("+", "").strip()
                # Remove nested button/sub-item artifacts
                clean_values = []
                for td in tds[1:]:
                    val_str = td.get_text(strip=True).replace(",", "").replace("%", "")
                    try:
                        clean_values.append(float(val_str))
                    except ValueError:
                        clean_values.append(val_str)
                rows[row_label] = clean_values

        return {"periods": headers, "rows": rows}

    def _parse_screener_html(self, html: str, ticker: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")

        # Extract Company Name
        company_name = ticker
        name_tag = soup.find("h1")
        if name_tag:
            company_name = name_tag.get_text(strip=True)

        # Extract Key Ratios from top widget
        ratios = {}
        ratio_items = soup.find_all("li", class_="flex")
        for item in ratio_items:
            name = item.find("span", class_="name")
            value = item.find("span", class_="nowrap")
            if name and value:
                ratios[name.get_text(strip=True)] = value.get_text(strip=True)

        # Parse Tables
        quarters_data = self._parse_table(soup, "quarters")
        balance_sheet_data = self._parse_table(soup, "balance-sheet")
        cash_flow_data = self._parse_table(soup, "cash-flow")

        return {
            "ticker": ticker,
            "company_name": company_name,
            "ratios": ratios,
            "quarters": quarters_data,
            "balance_sheet": balance_sheet_data,
            "cash_flow": cash_flow_data,
        }

if __name__ == "__main__":
    scraper = ScreenerScraper(use_cache=True)
    print("Testing ScreenerScraper on HINDUNILVR...")
    data = scraper.fetch_company_data("HINDUNILVR")
    print(f"Company: {data['company_name']}")
    print(f"Quarters available: {data['quarters'].get('periods', [])[-8:]}")
    if "Sales" in data['quarters'].get('rows', {}):
        print(f"Past 8Q Sales: {data['quarters']['rows']['Sales'][-8:]}")
