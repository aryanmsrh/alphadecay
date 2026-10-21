from typing import Any, Dict, List
from bs4 import BeautifulSoup
import httpx


class ScreenerScraper:
  HEADERS = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      ),
      "Accept": (
          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
      ),
  }

  def __init__(self, timeout: float = 14.0):
    self.timeout = timeout

  def fetch_company_data(self, ticker: str) -> Dict[str, Any]:
    clean_ticker = ticker.upper().strip()
    urls = [
        f"https://www.screener.in/company/{clean_ticker}/consolidated/",
        f"https://www.screener.in/company/{clean_ticker}/",
    ]

    best_parsed = None
    with httpx.Client(
        headers=self.HEADERS, timeout=self.timeout, follow_redirects=True
    ) as client:
      for url in urls:
        try:
          res = client.get(url)
          if res.status_code == 200 and len(res.text) > 1000:
            parsed = self._parse_html(res.text, clean_ticker, str(res.url))
            q_periods = parsed.get("quarters", {}).get("periods", [])
            pl_periods = parsed.get("profit_loss", {}).get("periods", [])
            if len(q_periods) >= 2 or len(pl_periods) >= 2:
              return parsed
            if best_parsed is None:
              best_parsed = parsed
        except Exception:
          continue

    if best_parsed is not None:
      return best_parsed

    raise RuntimeError(
        f"Could not retrieve financial data for ticker '{clean_ticker}' from"
        " Screener.in"
    )

  def _parse_table(self, soup: BeautifulSoup, section_id: str) -> Dict[str, Any]:
    section = soup.find("section", id=section_id)
    if not section:
      return {"periods": [], "rows": {}}

    table = section.find("table")
    if not table:
      return {"periods": [], "rows": {}}

    headers: List[str] = []
    thead = table.find("thead")
    if thead:
      for th in thead.find_all("th"):
        text = th.get_text(strip=True)
        if text:
          headers.append(text)

    rows: Dict[str, List[Any]] = {}
    tbody = table.find("tbody")
    if tbody:
      for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
          continue
        raw_label = tds[0].get_text(strip=True).replace("+", "")
        clean_label = " ".join(raw_label.split()).strip()
        values: List[Any] = []
        for td in tds[1:]:
          raw_val = td.get_text(strip=True).replace(",", "").replace("%", "")
          try:
            values.append(float(raw_val))
          except ValueError:
            values.append(raw_val)
        if clean_label:
          rows[clean_label] = values
          no_spaces = clean_label.replace(" ", "")
          if no_spaces != clean_label:
            rows[no_spaces] = values

    return {"periods": headers, "rows": rows}

  def _parse_html(
      self, html: str, ticker: str, source_url: str
  ) -> Dict[str, Any]:
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
        low_text = text.lower()
        low_href = href.lower()
        if (
            "transcript" in low_text
            or "transcript" in low_href
            or "concall" in low_text
        ) and href:
          if href.startswith("/"):
            href = f"https://www.screener.in{href}"
          concall_transcripts.append(
              {"title": text or "Concall Transcript", "url": href}
          )

    return {
        "ticker": ticker,
        "company_name": company_name,
        "source_url": source_url,
        "quarters": quarters,
        "profit_loss": profit_loss,
        "balance_sheet": balance_sheet,
        "cash_flow": cash_flow,
        "ratios_table": ratios_table,
        "concall_transcripts": concall_transcripts,
    }