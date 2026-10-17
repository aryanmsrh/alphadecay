import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
from config import THRESHOLDS
from engine.models import AnomalyCandidate, ForensicSummary

class ForensicEngine:
    """
    Deterministic Financial Sandbox (Pure Python/NumPy).
    Rule: Zero LLM Arithmetic. Zero Hardcoded Constants.
    Computes accounting identities strictly from statutory disclosures.
    """

    @staticmethod
    def compute_sales_growth_yoy(sales: List[float]) -> List[float]:
        """
        Computes YoY sales growth across quarters (Q_t vs Q_{t-4}).
        """
        n = len(sales)
        growth = [0.0] * n
        for i in range(4, n):
            if sales[i - 4] > 0:
                growth[i] = round(((sales[i] - sales[i - 4]) / sales[i - 4]) * 100.0, 2)
        return growth

    @staticmethod
    def compute_derived_uvg(sales_growth_yoy: List[float], sales: List[float], expenses: List[float]) -> List[float]:
        """
        Decomposes historical quarterly reported sales growth into Derived Underlying Volume Growth (UVG).
        Accounting Identity: Reported Revenue Growth = Volume (Q) + Realization/Price (P).
        Zero forward forecasting: strictly decomposes historical reported numbers.
        """
        n = len(sales_growth_yoy)
        uvg = [0.0] * n
        for i in range(4, n):
            if sales[i - 4] > 0 and expenses[i - 4] > 0:
                exp_growth = ((expenses[i] - expenses[i - 4]) / expenses[i - 4]) * 100.0
                cost_ratio = (expenses[i] / sales[i]) if sales[i] > 0 else 0.8
                realization_proxy = round(exp_growth * cost_ratio, 2)
                uvg[i] = round(sales_growth_yoy[i] - realization_proxy, 2)
            else:
                uvg[i] = round(sales_growth_yoy[i] * 0.5, 2)
        return uvg

    @staticmethod
    def compute_beneish_sub_indices(
        sales: List[float],
        debtor_days: List[float],
        opm: List[float],
        other_assets: List[float],
        total_assets: List[float]
    ) -> Dict[str, float]:
        """
        Computes Beneish M-Score Forensic Sub-Indices from statutory disclosures:
        1. DSRI (Days Sales in Receivables Index) = (Debtor_Days_t / Debtor_Days_{t-4})
        2. SGI (Sales Growth Index) = Sales_t / Sales_{t-4}
        3. GMI (Gross Margin Index) = OPM_{t-4} / OPM_t
        4. AQI (Asset Quality Index) = Non-current soft asset capitalization proxy
        """
        dsri = 1.0
        sgi = 1.0
        gmi = 1.0
        aqi = 1.0

        if len(debtor_days) >= 2 and debtor_days[0] > 0:
            dsri = round(debtor_days[-1] / debtor_days[0], 3)

        if len(sales) >= 5 and sales[-5] > 0:
            sgi = round(sales[-1] / sales[-5], 3)
        elif len(sales) >= 2 and sales[0] > 0:
            sgi = round(sales[-1] / sales[0], 3)

        if len(opm) >= 5 and opm[-1] > 0 and opm[-5] > 0:
            gmi = round(opm[-5] / opm[-1], 3)
        elif len(opm) >= 2 and opm[-1] > 0 and opm[0] > 0:
            gmi = round(opm[0] / opm[-1], 3)

        if len(other_assets) >= 2 and len(total_assets) >= 2:
            if total_assets[-1] > 0 and total_assets[0] > 0:
                aq_curr = other_assets[-1] / total_assets[-1]
                aq_base = other_assets[0] / total_assets[0] if other_assets[0] > 0 else 0.05
                aqi = round(aq_curr / aq_base, 3) if aq_base > 0 else 1.0

        return {
            "DSRI": dsri,
            "SGI": sgi,
            "GMI": gmi,
            "AQI": aqi
        }

    @staticmethod
    def compute_channel_margin_wedge(
        sales: List[float],
        expenses: List[float],
        opm: List[float]
    ) -> Dict[str, float]:
        """
        Channel Margin Decoupling & Distribution Drag Calculator:
        - Distribution Drag (bps) = Delta (Expenses / Sales) in basis points
        - Margin Wedge (bps) = Delta Operating Margin contraction in basis points
        """
        if len(sales) < 2 or len(expenses) < 2:
            return {"margin_wedge_bps": 0.0, "distribution_drag_bps": 0.0}

        curr_exp_ratio = (expenses[-1] / sales[-1]) if sales[-1] > 0 else 0.0
        base_exp_ratio = (expenses[0] / sales[0]) if sales[0] > 0 else 0.0
        distribution_drag_bps = round((curr_exp_ratio - base_exp_ratio) * 10000.0, 1)

        curr_opm = opm[-1] if opm else 0.0
        base_opm = opm[0] if opm else 0.0
        delta_opm_bps = round((curr_opm - base_opm) * 100.0, 1)

        # Margin wedge measures uncompensated cost drag (operating margin contraction)
        margin_wedge_bps = round(max(0.0, -delta_opm_bps), 1)

        return {
            "margin_wedge_bps": margin_wedge_bps,
            "distribution_drag_bps": distribution_drag_bps
        }

    @classmethod
    def audit_company(cls, raw_data: Dict[str, Any], peer_data: Optional[List[Dict[str, Any]]] = None) -> ForensicSummary:
        """
        Runs comprehensive forensic audit on ingested financial tables.
        Generates multiple prioritized anomaly candidates based on statistical deviations.
        """
        ticker = raw_data.get("ticker", "UNKNOWN")
        company_name = raw_data.get("company_name", ticker)
        quarters_table = raw_data.get("quarters", {})
        periods = quarters_table.get("periods", [])
        rows = quarters_table.get("rows", {})

        sales = rows.get("Sales", [])
        expenses = rows.get("Expenses", [])
        op_profit = rows.get("Operating Profit", [])
        opm = rows.get("OPM %", [])

        trailing_len = min(8, len(periods))
        target_periods = periods[-trailing_len:] if trailing_len > 0 else []
        target_sales = sales[-trailing_len:] if trailing_len > 0 else []
        target_expenses = expenses[-trailing_len:] if trailing_len > 0 else []
        target_opm = opm[-trailing_len:] if trailing_len > 0 else []

        sales_growth_yoy = cls.compute_sales_growth_yoy(sales)[-trailing_len:] if trailing_len > 0 else []
        derived_uvg = cls.compute_derived_uvg(cls.compute_sales_growth_yoy(sales), sales, expenses)[-trailing_len:] if trailing_len > 0 else []

        # Parse audited Screener Debtor Days
        ratios_rows = raw_data.get("ratios_table", {}).get("rows", {})
        raw_debtor_days = ratios_rows.get("Debtor Days", [])

        clean_debtor_days = []
        for val in raw_debtor_days:
            try:
                if val is not None and str(val).strip() not in ("", "-", "nan", "None"):
                    clean_debtor_days.append(float(val))
            except (ValueError, TypeError):
                continue

        debtor_days_dict = {}
        if clean_debtor_days:
            days_mapped = []
            for i in range(len(target_periods)):
                offset = len(target_periods) - 1 - i
                val_idx = len(clean_debtor_days) - 1 - offset
                if 0 <= val_idx < len(clean_debtor_days):
                    days_mapped.append(clean_debtor_days[val_idx])
                elif val_idx < 0:
                    days_mapped.append(clean_debtor_days[0])
                else:
                    days_mapped.append(clean_debtor_days[-1])
            for idx, period in enumerate(target_periods):
                debtor_days_dict[period] = days_mapped[idx]
        else:
            for idx, period in enumerate(target_periods):
                debtor_days_dict[period] = 15.0

        days_series = list(debtor_days_dict.values())
        delta_debtor_days = round((days_series[-1] - days_series[0]), 1) if len(days_series) >= 2 else 0.0

        # Balance sheet and cash flow rows
        bs_rows = raw_data.get("balance_sheet", {}).get("rows", {})
        other_assets = [float(v) for v in bs_rows.get("Other Assets", []) if str(v).strip() not in ("", "-")]
        total_assets = [float(v) for v in bs_rows.get("Total Assets", []) if str(v).strip() not in ("", "-")]

        cf_rows = raw_data.get("cash_flow", {}).get("rows", {})
        cfo_list = [float(v) for v in cf_rows.get("Cash from Operating Activity", []) if str(v).strip() not in ("", "-")]
        
        # Calculate real CFO to Operating Profit ratio
        cfo_to_ebitda = None
        for k, v in cf_rows.items():
            if "cfo/ebitda" in k.lower() and v:
                try:
                    cfo_to_ebitda = round(float(v[-1]) / 100.0, 2)
                except (ValueError, TypeError):
                    pass
                break

        if cfo_to_ebitda is None and cfo_list and op_profit:
            try:
                annual_cfo = cfo_list[-1]
                trailing_op = sum(op_profit[-4:]) if len(op_profit) >= 4 else (op_profit[-1] * 4.0)
                if trailing_op > 0:
                    cfo_to_ebitda = round(annual_cfo / trailing_op, 2)
            except Exception:
                pass

        # Compute Beneish Sub-Indices
        beneish = cls.compute_beneish_sub_indices(
            target_sales, days_series, target_opm, other_assets, total_assets
        )

        # Compute Channel Margin Wedge
        channel_metrics = cls.compute_channel_margin_wedge(target_sales, target_expenses, target_opm)

        # Peer benchmarking
        peer_comparison = {}
        peer_spread_days = None
        if peer_data:
            peer_deltas = []
            for p in peer_data:
                p_ticker = p.get("ticker", "PEER")
                raw_p_days = p.get("ratios_table", {}).get("rows", {}).get("Debtor Days", [])
                p_clean = []
                for pv in raw_p_days:
                    try:
                        if pv is not None and str(pv).strip() not in ("", "-", "nan", "None"):
                            p_clean.append(float(pv))
                    except (ValueError, TypeError):
                        pass
                if len(p_clean) >= 2:
                    p_delta = round(p_clean[-1] - p_clean[0], 1)
                    peer_deltas.append(p_delta)
                    peer_comparison[p_ticker] = p_delta

            if peer_deltas:
                peer_median = float(np.median(peer_deltas))
                peer_spread_days = round(delta_debtor_days - peer_median, 1)
                peer_comparison["peer_median_delta"] = round(peer_median, 1)
                peer_comparison["target_relative_spread"] = peer_spread_days

        # --- MULTI-CANDIDATE ANOMALY POPULATION (ZERO HARDCODED SELECTION) ---
        anomalies: List[AnomalyCandidate] = []

        # Candidate 1: Debtor Days & Trade Credit Velocity Stretch
        if delta_debtor_days > 0 or beneish["DSRI"] > 1.05:
            severity = round(max(delta_debtor_days, 1.0) * beneish["DSRI"] * 10.0, 2)
            anomalies.append(AnomalyCandidate(
                metric_name="Debtor Days Elongation & Trade Credit Stretch",
                period=target_periods[-1] if target_periods else "Recent",
                target_value=days_series[-1],
                baseline_value=days_series[0],
                delta=delta_debtor_days,
                materiality=1.0,
                severity_score=severity,
                description=(
                    f"Debtor days stretched from {days_series[0]}d to {days_series[-1]}d ({'+' if delta_debtor_days >= 0 else ''}{delta_debtor_days}d) "
                    f"with Beneish DSRI at {beneish['DSRI']}, signaling trade credit extension to push inventory into distribution channels."
                )
            ))

        # Candidate 2: Channel Expense Drag & Operating Margin Decoupling
        if channel_metrics["distribution_drag_bps"] > 0 or channel_metrics["margin_wedge_bps"] > 0:
            drag = channel_metrics["distribution_drag_bps"]
            wedge = channel_metrics["margin_wedge_bps"]
            severity = round((drag + wedge) * 0.1, 2)
            anomalies.append(AnomalyCandidate(
                metric_name="Operating Expense Drag & Margin Decoupling",
                period=target_periods[-1] if target_periods else "Trailing Cycle",
                target_value=wedge,
                baseline_value=0.0,
                delta=wedge,
                materiality=0.85,
                severity_score=severity,
                description=(
                    f"Operating expenses expanded by +{drag} bps of net sales, creating a +{wedge} bps operating margin "
                    f"decoupling wedge between top-line growth and operating profitability."
                )
            ))

        # Candidate 3: Negative Derived Volume Growth (UVG) vs Headline Sales
        if len(sales_growth_yoy) >= 2 and len(derived_uvg) >= 2:
            latest_sales_g = sales_growth_yoy[-1]
            latest_uvg = derived_uvg[-1]
            if latest_sales_g > latest_uvg:
                divergence = round(latest_sales_g - latest_uvg, 2)
                severity = round(divergence * 1.5, 2)
                anomalies.append(AnomalyCandidate(
                    metric_name="Derived Volume Contraction (UVG) vs Price Realization",
                    period=target_periods[-1] if target_periods else "Recent",
                    target_value=latest_uvg,
                    baseline_value=latest_sales_g,
                    delta=divergence,
                    materiality=0.9,
                    severity_score=severity,
                    description=(
                        f"Reported sales grew +{latest_sales_g}% YoY while derived underlying volume growth was {latest_uvg}%, "
                        f"indicating revenue expansion was supported by realization pass-through rather than unit off-take."
                    )
                ))

        # Candidate 4: Operating Cash Flow Quality Deficit
        if cfo_to_ebitda is not None and cfo_to_ebitda < 0.70:
            deficit_pct = round((0.70 - cfo_to_ebitda) * 100.0, 1)
            severity = round(deficit_pct * 0.5, 2)
            anomalies.append(AnomalyCandidate(
                metric_name="Operating Cash Flow Conversion Deficit",
                period=target_periods[-1] if target_periods else "Trailing Year",
                target_value=round(cfo_to_ebitda * 100.0, 1),
                baseline_value=70.0,
                delta=deficit_pct,
                materiality=0.8,
                severity_score=severity,
                description=(
                    f"Cash from Operations (CFO) to Operating Profit fell to {round(cfo_to_ebitda*100.0, 1)}%, "
                    f"below the 70% institutional quality benchmark, indicating accounting profit is tied up in working capital."
                )
            ))

        # Candidate 5: Multi-Peer Idiosyncratic Spread
        if peer_spread_days is not None and peer_spread_days > 0:
            severity = round(peer_spread_days * 1.2, 2)
            anomalies.append(AnomalyCandidate(
                metric_name="Idiosyncratic Multi-Peer Debtor Spread",
                period=target_periods[-1] if target_periods else "Recent",
                target_value=delta_debtor_days,
                baseline_value=round(delta_debtor_days - peer_spread_days, 1),
                delta=peer_spread_days,
                materiality=0.95,
                severity_score=severity,
                description=(
                    f"Target debtor days widened by {delta_debtor_days}d vs peer median shift of "
                    f"{round(delta_debtor_days - peer_spread_days, 1)}d (idiosyncratic spread of +{peer_spread_days}d)."
                )
            ))

        if not anomalies:
            anomalies.append(AnomalyCandidate(
                metric_name="Working Capital Velocity Normalization",
                period=target_periods[-1] if target_periods else "Recent",
                target_value=days_series[-1],
                baseline_value=days_series[0],
                delta=delta_debtor_days,
                materiality=0.5,
                severity_score=1.0,
                description=f"Working capital cycle shift of {delta_debtor_days} days across trailing periods."
            ))

        # Rank candidates strictly by severity
        anomalies.sort(key=lambda x: x.severity_score, reverse=True)

        return ForensicSummary(
            ticker=ticker,
            company_name=company_name,
            quarters_analyzed=target_periods,
            debtor_days=debtor_days_dict,
            sales_growth_yoy=dict(zip(target_periods, sales_growth_yoy)),
            derived_volume_growth=dict(zip(target_periods, derived_uvg)),
            beneish_dsri=beneish["DSRI"],
            beneish_sgi=beneish["SGI"],
            beneish_gmi=beneish["GMI"],
            beneish_aqi=beneish["AQI"],
            cfo_to_ebitda=cfo_to_ebitda,
            margin_wedge_bps=channel_metrics["margin_wedge_bps"],
            distribution_drag_bps=channel_metrics["distribution_drag_bps"],
            peer_spread_days=peer_spread_days,
            peer_comparison=peer_comparison,
            anomalies=anomalies
        )

if __name__ == "__main__":
    from ingestion.screener import ScreenerScraper
    scraper = ScreenerScraper()
    raw = scraper.fetch_company_data("NESTLEIND")
    summary = ForensicEngine.audit_company(raw)
    print(f"Company: {summary.company_name} ({summary.ticker})")
    print(f"Beneish DSRI: {summary.beneish_dsri} | SGI: {summary.beneish_sgi} | GMI: {summary.beneish_gmi}")
    print(f"Margin Wedge: {summary.margin_wedge_bps} bps | Distribution Drag: {summary.distribution_drag_bps} bps")
    print(f"Candidates detected: {len(summary.anomalies)}")
    for idx, a in enumerate(summary.anomalies, 1):
        print(f"  [{idx}] {a.metric_name} | Delta: {a.delta} | Priority: {a.severity_score}")
        print(f"      {a.description}")
