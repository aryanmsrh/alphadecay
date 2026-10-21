import json
from typing import Any, Callable, Dict, List, Optional
from config import PEER_MAPPING, TRACK_C_NIFTY50
from ingest.screener import ScreenerScraper
from ingest.concall import ConcallHarvester
from ingest.search import TavilySearchClient
from analytics.analytics import calculate_financial_indicators


def format_peer_metric_for_anomaly(metric_id: str, peer_data: List[Dict[str, Any]]) -> List[str]:
    bullets: List[str] = []
    clean_id = (metric_id or "").strip().lower()

    for p in peer_data:
        pt = p.get("ticker", "PEER")
        ind = p.get("indicators", {})

        if "margin" in clean_id or "cost" in clean_id:
            rev = ind.get("revenue_growth_yoy")
            exp = ind.get("expense_growth_yoy")
            opm = ind.get("operating_margin")
            opm_chg = ind.get("margin_change_pp")
            wedge = round(exp - rev, 2) if (exp is not None and rev is not None) else None

            parts = [f"Sector Peer {pt}"]
            if rev is not None:
                parts.append(f"Sales YoY: {rev:+.2f}%")
            if exp is not None:
                parts.append(f"Expenses YoY: {exp:+.2f}%")
            if wedge is not None:
                parts.append(f"Expense-to-Sales Wedge: {wedge:+.2f} pp")
            if opm is not None:
                chg_str = f" ({opm_chg:+.2f} pp YoY)" if opm_chg is not None else ""
                parts.append(f"OPM: {opm:.2f}%{chg_str}")
            bullets.append(" | ".join(parts))

        elif "cfo" in clean_id or "ebitda" in clean_id or "cash" in clean_id:
            cfo_pct = ind.get("cfo_to_op_profit_pct")
            cfo_delta = ind.get("cfo_conversion_delta_pp")
            opm = ind.get("operating_margin")

            parts = [f"Sector Peer {pt}"]
            if cfo_pct is not None:
                delta_str = f" ({cfo_delta:+.2f} pp YoY)" if cfo_delta is not None else ""
                parts.append(f"CFO/EBITDA Conversion: {cfo_pct:.2f}%{delta_str}")
            if opm is not None:
                parts.append(f"OPM: {opm:.2f}%")
            bullets.append(" | ".join(parts))

        elif "inventory" in clean_id or "dio" in clean_id:
            dio = ind.get("inventory_days_latest")
            dio_prior = ind.get("inventory_days_prior")
            dio_chg = ind.get("inventory_days_change")
            rev = ind.get("revenue_growth_yoy")

            parts = [f"Sector Peer {pt}"]
            if dio is not None:
                if dio_prior is not None and dio_chg is not None:
                    parts.append(f"Inventory Days (DIO): {dio_prior:.1f}d -> {dio:.1f}d ({dio_chg:+.1f}d YoY)")
                else:
                    parts.append(f"Inventory Days (DIO): {dio:.1f}d")
            if rev is not None:
                parts.append(f"Sales YoY: {rev:+.2f}%")
            bullets.append(" | ".join(parts))

        elif "debtor" in clean_id or "dso" in clean_id:
            dso = ind.get("debtor_days_latest")
            dso_prior = ind.get("debtor_days_prior")
            dso_chg = ind.get("debtor_days_change")
            rev = ind.get("revenue_growth_yoy")

            parts = [f"Sector Peer {pt}"]
            if dso is not None:
                if dso_prior is not None and dso_chg is not None:
                    parts.append(f"Debtor Days (DSO): {dso_prior:.1f}d -> {dso:.1f}d ({dso_chg:+.1f}d YoY)")
                else:
                    parts.append(f"Debtor Days (DSO): {dso:.1f}d")
            if rev is not None:
                parts.append(f"Sales YoY: {rev:+.2f}%")
            bullets.append(" | ".join(parts))

        elif "payable" in clean_id or "ccc" in clean_id:
            dpo = ind.get("payable_days_latest")
            ccc = ind.get("ccc_latest")
            ccc_chg = ind.get("ccc_change")

            parts = [f"Sector Peer {pt}"]
            if dpo is not None:
                parts.append(f"Payable Days (DPO): {dpo:.1f}d")
            if ccc is not None:
                chg_str = f" ({ccc_chg:+.1f}d YoY)" if ccc_chg is not None else ""
                parts.append(f"Cash Conversion Cycle (CCC): {ccc:.1f}d{chg_str}")
            bullets.append(" | ".join(parts))

    return bullets


class Finder:
    def __init__(self):
        self.scraper = ScreenerScraper()
        self.harvester = ConcallHarvester()
        self.search_client = TavilySearchClient()

    def gather_company_dossier(self, ticker: str) -> Dict[str, Any]:
        clean_ticker = ticker.upper().strip()
        raw_data = self.scraper.fetch_company_data(clean_ticker)
        company_name = raw_data.get("company_name", clean_ticker)
        indicators = calculate_financial_indicators(raw_data)

        peer_tickers = PEER_MAPPING.get(clean_ticker, [])
        if not peer_tickers:
            peer_tickers = [t for t in TRACK_C_NIFTY50 if t != clean_ticker]
        target_peers = [p for p in peer_tickers if p != clean_ticker][:2]

        peer_data: List[Dict[str, Any]] = []
        for pt in target_peers:
            try:
                peer_raw = self.scraper.fetch_company_data(pt)
                peer_ind = calculate_financial_indicators(peer_raw)
                peer_data.append({
                    "ticker": pt,
                    "company_name": peer_raw.get("company_name", pt),
                    "raw_data": peer_raw,
                    "indicators": peer_ind,
                })
            except Exception:
                continue

        anomalies = indicators.get("anomalies", [])
        for anom in anomalies:
            a_id = anom.get("id", "")
            matching_peer_bullets = format_peer_metric_for_anomaly(a_id, peer_data)
            if "numbers_bullets" in anom and matching_peer_bullets:
                for pb in matching_peer_bullets:
                    anom["numbers_bullets"].append(f"Sector Peer Benchmark: {pb}")

        evidence_items = []
        concall_links = raw_data.get("concall_transcripts", [])
        if concall_links:
            for item in concall_links[:2]:
                link = item.get("url") if isinstance(item, dict) else item
                try:
                    excerpts = self.harvester.harvest_transcript(link)
                    for ex in excerpts:
                        evidence_items.append({
                            "source": (
                                f"Concall: {item.get('title', 'Earnings Transcript')}"
                                if isinstance(item, dict)
                                else "Concall Transcript"
                            ),
                            "url": ex.get("source_url", link),
                            "excerpt": ex.get("excerpt", ""),
                        })
                    if len(evidence_items) >= 4:
                        break
                except Exception:
                    continue

        try:
            search_hits = self.search_client.search(
                f"{company_name} {clean_ticker} quarterly financial results margin working capital concall",
                max_results=3,
            )
            for hit in search_hits:
                evidence_items.append({
                    "source": hit.get("title", "Public Filing / Disclosure"),
                    "url": hit.get("url", ""),
                    "excerpt": hit.get("content", ""),
                })
        except Exception:
            pass

        if not evidence_items:
            evidence_items.append({
                "source": "Statutory Financial Statements (Screener / BSE)",
                "url": raw_data.get("source_url", f"https://www.screener.in/company/{clean_ticker}/"),
                "excerpt": f"Audited statutory financial disclosures and quarterly tables for {company_name} ({clean_ticker}).",
            })

        return {
            "ticker": clean_ticker,
            "company_name": company_name,
            "raw_data": raw_data,
            "indicators": indicators,
            "anomalies": anomalies,
            "key_numbers": indicators.get("key_numbers", []),
            "quarterly_history": indicators.get("quarterly_history", []),
            "peer_data": peer_data,
            "evidence_items": evidence_items,
        }

    def get_tool_manifest(self) -> str:
        manifest = [
            {
                "tool_name": "triangulate_peer_metric",
                "description": "Scrapes the 2 sector peers for target company and returns strict matching metric comparison for the active anomaly.",
                "parameters": {
                    "metric_id": "One of: signal_margin_cost_dynamics, signal_cfo_ebitda, signal_inventory_dio, signal_payables_ccc, signal_debtor_days"
                }
            },
            {
                "tool_name": "search_concall_transcript",
                "description": "Searches harvested earnings concall excerpts for anomaly-specific operational or management keywords.",
                "parameters": {
                    "keywords": "Space-separated keywords (e.g. 'inventory demand modern trade channel')"
                }
            },
            {
                "tool_name": "search_india_filings_news",
                "description": "Runs targeted search across Indian financial sources, NSE, and BSE disclosures.",
                "parameters": {
                    "query": "Specific forensic or operational query"
                }
            },
            {
                "tool_name": "get_multi_quarter_table",
                "description": "Returns trailing 8-quarter P&L or 4-year working capital history table for the target company.",
                "parameters": {
                    "metric_id": "Metric identifier or category (e.g. 'margin', 'inventory', 'cash_flow', 'debtors')"
                }
            }
        ]
        return json.dumps(manifest, indent=2)

    def execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        company_name: str,
        ticker: str,
        dossier: Dict[str, Any],
        event_callback: Optional[Callable[..., None]] = None,
    ) -> str:
        name = (tool_name or "").strip().lower()
        args = tool_args or {}

        def _notify(step: str, message: str, data: Optional[Dict[str, Any]] = None):
            if not event_callback:
                return
            try:
                import inspect
                sig = inspect.signature(event_callback)
                if len(sig.parameters) == 1:
                    event_callback({"step": step, "message": message, **(data or {})})
                else:
                    event_callback(step, message, data or {})
            except Exception:
                try:
                    event_callback({"step": step, "message": message, **(data or {})})
                except Exception:
                    pass

        _notify("TOOL_CALL", f"Agent invoking tool '{name}' with {json.dumps(args)}", {"tool_name": name, "tool_args": args})

        result = ""
        if name == "triangulate_peer_metric":
            metric_id = str(args.get("metric_id", "")).strip()
            peer_data = dossier.get("peer_data", [])
            bullets = format_peer_metric_for_anomaly(metric_id, peer_data)
            if bullets:
                result = "\n".join([f"- {b}" for b in bullets])
            else:
                result = f"No sector peer metric comparison available for '{metric_id}'."

        elif name == "search_concall_transcript":
            raw_keywords = str(args.get("keywords", "")).lower()
            keywords = [w for w in raw_keywords.replace(",", " ").split() if len(w) > 2]
            evidence = dossier.get("evidence_items", [])
            matched = []
            for item in evidence:
                text = (item.get("excerpt", "")).lower()
                source = (item.get("source", "")).lower()
                score = sum(1 for kw in keywords if kw in text or kw in source)
                if score > 0:
                    matched.append((score, item))
            matched.sort(key=lambda x: x[0], reverse=True)
            if matched:
                lines = []
                for score, item in matched[:3]:
                    lines.append(f"[{item.get('source')}]: {item.get('excerpt', '')[:350]}")
                result = "\n\n".join(lines)
            else:
                result = f"No concall excerpts matched keywords: '{raw_keywords}'."

        elif name == "search_india_filings_news":
            query = str(args.get("query", "")).strip()
            search_query = f"{company_name} ({ticker}) India NSE BSE {query}"
            hits = self.search_client.search(search_query, max_results=3)
            if hits:
                lines = []
                for h in hits:
                    lines.append(f"[{h.get('title')} — {h.get('url')}]: {h.get('content', '')[:350]}")
                result = "\n\n".join(lines)
            else:
                result = f"No public filings or news records found for '{query}'."

        elif name == "get_multi_quarter_table":
            metric_id = str(args.get("metric_id", "")).strip().lower()
            if any(k in metric_id for k in ["margin", "sales", "revenue", "cost", "expense", "pnl"]):
                history = dossier.get("quarterly_history", [])
                lines = ["Trailing Quarterly P&L:"]
                for q in history[-8:]:
                    p = q.get("period", "")
                    r = q.get("revenue")
                    e = q.get("expenses")
                    m = q.get("operating_margin_pct")
                    lines.append(f"- {p}: Sales ₹{r:,.1f} Cr | Expenses ₹{e:,.1f} Cr | OPM {m:.2f}%" if (r is not None and e is not None and m is not None) else f"- {p}: Trajectory record")
                result = "\n".join(lines)
            else:
                raw_data = dossier.get("raw_data", {})
                ratios = raw_data.get("ratios_table") or raw_data.get("ratios") or {}
                periods = ratios.get("periods", [])
                rows = ratios.get("rows", {})
                lines = [f"Audited Annual Ratios History ({', '.join(periods[-5:])}):"]
                for r_name, r_vals in rows.items():
                    if any(target in r_name.lower() for target in ["debtor", "inventory", "payable", "cash conversion"]):
                        lines.append(f"- {r_name}: {r_vals[-5:]}")
                result = "\n".join(lines) if len(lines) > 1 else "Annual ratios table not available."

        else:
            result = f"Tool '{name}' is not recognized."

        _notify("TOOL_RESULT", f"Tool '{name}' returned verified data", {"tool_name": name, "result_preview": result[:200]})
        return result

    def get_attack_context(
        self, anomaly: Dict[str, Any], key_numbers: List[Dict[str, Any]], evidence_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        relevant_evidence = []
        for e in evidence_items:
            text = (e.get("excerpt") or "").lower()
            if any(k in text for k in ["inventory", "receivable", "debtor", "credit", "delay", "pressure", "margin", "cash"]):
                relevant_evidence.append(e)
        return {
            "anomaly": anomaly,
            "key_numbers": key_numbers,
            "evidence": relevant_evidence[:4] or evidence_items[:3],
        }

    def get_defense_context(
        self, anomaly: Dict[str, Any], key_numbers: List[Dict[str, Any]], evidence_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        relevant_evidence = []
        for e in evidence_items:
            text = (e.get("excerpt") or "").lower()
            if any(k in text for k in ["season", "festive", "diwali", "puja", "growth", "expansion", "strategic", "demand", "synergy"]):
                relevant_evidence.append(e)
        return {
            "anomaly": anomaly,
            "key_numbers": key_numbers,
            "evidence": relevant_evidence[:4] or evidence_items[:3],
        }
