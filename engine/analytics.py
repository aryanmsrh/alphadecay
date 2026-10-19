import re
from typing import Dict, Any, List, Optional, Tuple

MONTH_NAMES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
}


def parse_period_key(period_str: str) -> Optional[Tuple[int, int]]:
    parts = period_str.strip().split()
    if len(parts) == 2:
        m_str = parts[0].lower()
        if m_str in MONTH_NAMES and parts[1].isdigit():
            return int(parts[1]), MONTH_NAMES[m_str]
    return None


def find_yoy_prior_period(target_period: str, all_periods: List[str]) -> Optional[str]:
    parsed = parse_period_key(target_period)
    if not parsed:
        return None
    target_year, target_month = parsed
    prior_year = target_year - 1
    for p in all_periods:
        p_parsed = parse_period_key(p)
        if p_parsed and p_parsed == (prior_year, target_month):
            return p
    return None


def calculate_percentage_growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous <= 0:
        return None
    return round(((current - previous) / previous) * 100.0, 2)


def calculate_operating_margin(operating_profit: Optional[float], revenue: Optional[float]) -> Optional[float]:
    if operating_profit is None or revenue is None or revenue <= 0:
        return None
    return round((operating_profit / revenue) * 100.0, 2)


def calculate_financial_indicators(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    ticker = raw_data.get("ticker", "").upper().strip()
    company_name = raw_data.get("company_name", ticker)
    quarters = raw_data.get("quarters", {})
    periods = quarters.get("periods", [])
    rows = quarters.get("rows", {})

    sales_series = rows.get("Sales", [])
    expenses_series = rows.get("Expenses", [])
    operating_profit_series = rows.get("Operating Profit", [])
    opm_series = rows.get("OPM %", [])

    sales_by_period = {}
    expenses_by_period = {}
    operating_profit_by_period = {}
    opm_by_period = {}

    for idx, p in enumerate(periods):
        if idx < len(sales_series) and isinstance(sales_series[idx], (int, float)):
            sales_by_period[p] = float(sales_series[idx])
        if idx < len(expenses_series) and isinstance(expenses_series[idx], (int, float)):
            expenses_by_period[p] = float(expenses_series[idx])
        if idx < len(operating_profit_series) and isinstance(operating_profit_series[idx], (int, float)):
            operating_profit_by_period[p] = float(operating_profit_series[idx])
        if idx < len(opm_series) and isinstance(opm_series[idx], (int, float)):
            opm_by_period[p] = float(opm_series[idx])

    quarterly_history = []
    trailing_periods = periods[-8:] if len(periods) >= 8 else periods

    for p in trailing_periods:
        rev = sales_by_period.get(p)
        exp = expenses_by_period.get(p)
        op = operating_profit_by_period.get(p)
        margin = opm_by_period.get(p)
        if margin is None and rev and op:
            margin = calculate_operating_margin(op, rev)

        quarterly_history.append({
            "period": p,
            "revenue": rev,
            "expenses": exp,
            "operating_profit": op,
            "operating_margin_pct": margin
        })

    latest_period = periods[-1] if periods else "Latest"
    prior_yoy_period = find_yoy_prior_period(latest_period, periods)

    current_sales = sales_by_period.get(latest_period)
    prior_sales = sales_by_period.get(prior_yoy_period) if prior_yoy_period else None
    revenue_growth_yoy = calculate_percentage_growth(current_sales, prior_sales)

    current_expenses = expenses_by_period.get(latest_period)
    prior_expenses = expenses_by_period.get(prior_yoy_period) if prior_yoy_period else None
    expense_growth_yoy = calculate_percentage_growth(current_expenses, prior_expenses)

    current_op = operating_profit_by_period.get(latest_period)
    current_margin = calculate_operating_margin(current_op, current_sales)
    prior_op = operating_profit_by_period.get(prior_yoy_period) if prior_yoy_period else None
    prior_margin = calculate_operating_margin(prior_op, prior_sales)

    margin_change_pp = None
    if current_margin is not None and prior_margin is not None:
        margin_change_pp = round(current_margin - prior_margin, 2)

    # Extract annual Profit & Loss and Cash Flow statements
    pl_data = raw_data.get("profit_loss", {})
    pl_periods = pl_data.get("periods", [])
    pl_rows = pl_data.get("rows", {})
    pl_sales = pl_rows.get("Sales", [])
    pl_op = pl_rows.get("Operating Profit", [])
    pl_expenses = pl_rows.get("Expenses", [])

    cf_data = raw_data.get("cash_flow", {})
    cf_periods = cf_data.get("periods", [])
    cf_rows = cf_data.get("rows", {})
    cfo_series_raw = cf_rows.get("Cash from Operating Activity", [])

    # Map annual P&L and Cash Flow by audited year (excluding 'TTM' for cash flow matching)
    pl_op_by_period = {}
    pl_sales_by_period = {}
    for idx, p in enumerate(pl_periods):
        if p != "TTM" and idx < len(pl_op) and isinstance(pl_op[idx], (int, float)):
            pl_op_by_period[p] = float(pl_op[idx])
        if p != "TTM" and idx < len(pl_sales) and isinstance(pl_sales[idx], (int, float)):
            pl_sales_by_period[p] = float(pl_sales[idx])

    cfo_by_period = {}
    for idx, p in enumerate(cf_periods):
        if idx < len(cfo_series_raw) and isinstance(cfo_series_raw[idx], (int, float)):
            cfo_by_period[p] = float(cfo_series_raw[idx])

    # Find common audited annual periods between Cash Flow and Profit & Loss
    common_annual_periods = [p for p in cf_periods if p in pl_op_by_period and p in cfo_by_period]
    latest_annual_period = common_annual_periods[-1] if common_annual_periods else None
    prior_annual_period = common_annual_periods[-2] if len(common_annual_periods) >= 2 else None
    two_prior_annual_period = common_annual_periods[-3] if len(common_annual_periods) >= 3 else None

    # Calculate exact annual CFO Conversion Ratios (No quarterly extrapolation!)
    latest_annual_cfo = cfo_by_period.get(latest_annual_period) if latest_annual_period else None
    latest_annual_op = pl_op_by_period.get(latest_annual_period) if latest_annual_period else None
    cfo_to_op_profit_pct = None
    if latest_annual_cfo is not None and latest_annual_op and latest_annual_op > 0:
        cfo_to_op_profit_pct = round((latest_annual_cfo / latest_annual_op) * 100.0, 2)

    prior_annual_cfo = cfo_by_period.get(prior_annual_period) if prior_annual_period else None
    prior_annual_op = pl_op_by_period.get(prior_annual_period) if prior_annual_period else None
    prior_cfo_to_op_profit_pct = None
    if prior_annual_cfo is not None and prior_annual_op and prior_annual_op > 0:
        prior_cfo_to_op_profit_pct = round((prior_annual_cfo / prior_annual_op) * 100.0, 2)

    two_prior_annual_cfo = cfo_by_period.get(two_prior_annual_period) if two_prior_annual_period else None
    two_prior_annual_op = pl_op_by_period.get(two_prior_annual_period) if two_prior_annual_period else None
    two_prior_cfo_to_op_profit_pct = None
    if two_prior_annual_cfo is not None and two_prior_annual_op and two_prior_annual_op > 0:
        two_prior_cfo_to_op_profit_pct = round((two_prior_annual_cfo / two_prior_annual_op) * 100.0, 2)

    # Ratios table parsing
    ratios_rows = raw_data.get("ratios_table", {}).get("rows", {})
    debtor_days_series = ratios_rows.get("Debtor Days", [])
    clean_debtor_days = [float(v) for v in debtor_days_series if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit())]
    debtor_days_latest = clean_debtor_days[-1] if clean_debtor_days else None
    debtor_days_prior = clean_debtor_days[-2] if len(clean_debtor_days) >= 2 else None
    debtor_days_change = None
    if debtor_days_latest is not None and debtor_days_prior is not None:
        debtor_days_change = round(debtor_days_latest - debtor_days_prior, 1)

    inv_days_series = ratios_rows.get("Inventory Days", [])
    clean_inv_days = [float(v) for v in inv_days_series if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit())]
    inv_days_latest = clean_inv_days[-1] if clean_inv_days else None
    inv_days_prior = clean_inv_days[-2] if len(clean_inv_days) >= 2 else None
    inv_days_change = round(inv_days_latest - inv_days_prior, 1) if (inv_days_latest is not None and inv_days_prior is not None) else None

    days_payable_series = ratios_rows.get("Days Payable", [])
    clean_payable_days = [float(v) for v in days_payable_series if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit())]
    payable_days_latest = clean_payable_days[-1] if clean_payable_days else None
    payable_days_prior = clean_payable_days[-2] if len(clean_payable_days) >= 2 else None

    ccc_series = ratios_rows.get("Cash Conversion Cycle", [])
    clean_ccc = [float(v) for v in ccc_series if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit())]
    ccc_latest = clean_ccc[-1] if clean_ccc else None
    ccc_prior = clean_ccc[-2] if len(clean_ccc) >= 2 else None

    wc_days_series = ratios_rows.get("Working Capital Days", [])
    clean_wc_days = [float(v) for v in wc_days_series if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit())]
    wc_days_latest = clean_wc_days[-1] if clean_wc_days else None
    wc_days_prior = clean_wc_days[-2] if len(clean_wc_days) >= 2 else None
    wc_days_change = round(wc_days_latest - wc_days_prior, 1) if (wc_days_latest is not None and wc_days_prior is not None) else None

    bs_rows = raw_data.get("balance_sheet", {}).get("rows", {})
    trade_rec_series = [float(v) for v in bs_rows.get("Trade Receivables", []) if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit())]
    receivables_growth_yoy = None
    if len(trade_rec_series) >= 2:
        receivables_growth_yoy = calculate_percentage_growth(trade_rec_series[-1], trade_rec_series[-2])

    # Formulate rigorous, descriptive Key Numbers with verified formulas
    cf_period_label = f"{latest_annual_period} vs {prior_annual_period}" if (latest_annual_period and prior_annual_period) else (latest_annual_period or "Annual Audited")

    key_numbers = [
        {
            "name": "Revenue Growth (YoY)",
            "value": f"{revenue_growth_yoy:+.2f}%" if revenue_growth_yoy is not None else "Data Insufficient",
            "period": f"Quarterly: {latest_period} vs {prior_yoy_period}" if prior_yoy_period else latest_period,
            "formula": "((Net_Sales_t - Net_Sales_t_minus_4) / Net_Sales_t_minus_4) * 100",
            "calculation_steps": f"(({current_sales:,.1f} Cr - {prior_sales:,.1f} Cr) / {prior_sales:,.1f} Cr) * 100 = {revenue_growth_yoy:+.2f}%" if (current_sales and prior_sales) else "Awaiting disclosures",
            "plain_english": "The percentage year-over-year rate of change in top-line net sales revenue compared to the exact same quarter last year.",
            "what_it_signifies": "Measures core commercial demand momentum and price realization across identical seasonal cycles, filtering out seasonal distortion."
        },
        {
            "name": "Operating Profit (EBITDA ex-Other Income) Margin",
            "value": f"{current_margin:.2f}%" if current_margin is not None else "Data Insufficient",
            "period": f"Quarterly: {latest_period}",
            "formula": "(Operating_Profit_ex_Other_Income / Net_Sales) * 100",
            "calculation_steps": f"({current_op:,.1f} Cr / {current_sales:,.1f} Cr) * 100 = {current_margin:.2f}%" if (current_op and current_sales) else "Awaiting disclosures",
            "plain_english": "Core operating profitability from commercial goods sold before financing costs, depreciation, non-operating treasury income, and direct taxes.",
            "what_it_signifies": "Isolates pure operating manufacturing and distribution profitability. Shows what percentage of each rupee earned remains after direct operating expenses."
        },
        {
            "name": "Operating Margin YoY Spread",
            "value": f"{margin_change_pp:+.2f} percentage points ({int(margin_change_pp * 100):+d} bps)" if margin_change_pp is not None else "Data Insufficient",
            "period": f"Quarterly: {latest_period} vs {prior_yoy_period}" if prior_yoy_period else latest_period,
            "formula": "Current_OPM - Prior_YoY_OPM",
            "calculation_steps": f"{current_margin:.2f}% - {prior_margin:.2f}% = {margin_change_pp:+.2f} pp ({int(margin_change_pp * 100):+d} bps)" if (current_margin is not None and prior_margin is not None) else "Awaiting disclosures",
            "plain_english": "The expansion or contraction in operating profit margin percentage points across a full 12-month seasonal cycle.",
            "what_it_signifies": "Quantifies operational cost leverage. A negative spread indicates input commodity inflation, freight, or ad-spends expanding faster than sales realization."
        },
        {
            "name": "Operating Expense Growth (YoY)",
            "value": f"{expense_growth_yoy:+.2f}%" if expense_growth_yoy is not None else "Data Insufficient",
            "period": f"Quarterly: {latest_period} vs {prior_yoy_period}" if prior_yoy_period else latest_period,
            "formula": "((Operating_Expenses_t - Operating_Expenses_t_minus_4) / Operating_Expenses_t_minus_4) * 100",
            "calculation_steps": f"(({current_expenses:,.1f} Cr - {prior_expenses:,.1f} Cr) / {prior_expenses:,.1f} Cr) * 100 = {expense_growth_yoy:+.2f}%" if (current_expenses and prior_expenses) else "Awaiting disclosures",
            "plain_english": "How fast total operating expenditures (raw material costs, employee overhead, advertising, freight) increased over the past 12 months.",
            "what_it_signifies": (
                f"Compared directly against top-line sales growth ({revenue_growth_yoy:+.2f}% vs {expense_growth_yoy:+.2f}%); when expense growth outpaces revenue growth, margins compress."
                if (revenue_growth_yoy is not None and expense_growth_yoy is not None)
                else "Compared directly against top-line sales growth; when expense growth outpaces revenue growth, margins compress."
            )
        },
        {
            "name": "Operating Cash Flow (CFO) to EBITDA Conversion",
            "value": f"{cfo_to_op_profit_pct:.2f}% of EBITDA" if cfo_to_op_profit_pct is not None else "Data Insufficient",
            "period": f"Audited Annual: {cf_period_label}",
            "formula": "(Audited_Annual_CFO / Audited_Annual_Operating_Profit_EBITDA) * 100",
            "calculation_steps": f"({latest_annual_cfo:,.1f} Cr / {latest_annual_op:,.1f} Cr) * 100 = {cfo_to_op_profit_pct:.2f}% (Prior {prior_annual_period}: {prior_cfo_to_op_profit_pct:.2f}%)" if (latest_annual_cfo is not None and latest_annual_op) else "Audited statutory disclosures",
            "plain_english": "The proportion of audited annual Operating Profit (EBITDA ex-Other Income) that actually materialized as physical cash flow from operations.",
            "what_it_signifies": (
                f"Rigorous earnings quality test matching identical audited annual periods. A sustained shift ({prior_annual_period}: {prior_cfo_to_op_profit_pct:.1f}% -> {latest_annual_period}: {cfo_to_op_profit_pct:.1f}%) indicates cash absorption into working capital."
                if (prior_cfo_to_op_profit_pct is not None and cfo_to_op_profit_pct is not None)
                else "Rigorous earnings quality test matching identical audited annual periods. A sustained decline indicates cash absorption into working capital."
            )
        },
        {
            "name": "Trade Receivables / Debtor Days (DSO)",
            "value": f"{debtor_days_latest:.1f} days ({debtor_days_change:+.1f}d shift)" if (debtor_days_latest is not None and debtor_days_change is not None) else (f"{debtor_days_latest:.1f} days" if debtor_days_latest is not None else "Data Insufficient"),
            "period": f"Audited Annual: {latest_annual_period or 'Latest'}",
            "formula": "(Trade_Receivables / Audited_Annual_Sales) * 365",
            "calculation_steps": f"Prior ({prior_annual_period}): {debtor_days_prior:.1f}d -> Current ({latest_annual_period}): {debtor_days_latest:.1f}d (Delta: {debtor_days_change:+.1f} days)" if (debtor_days_latest is not None and debtor_days_prior is not None) else "Audited balance sheet ratios",
            "plain_english": "The average number of days required for the company to collect cash from wholesale distributors and retail accounts after delivering goods.",
            "what_it_signifies": "Measures distributor credit discipline. Rising debtor days indicates trade partners delaying payments; falling days indicates disciplined cash collections."
        },
        {
            "name": "Days Inventory Outstanding (DIO)",
            "value": f"{inv_days_latest:.1f} days ({inv_days_change:+.1f}d shift)" if (inv_days_latest is not None and inv_days_change is not None) else (f"{inv_days_latest:.1f} days" if inv_days_latest is not None else "Data Insufficient"),
            "period": f"Audited Annual: {latest_annual_period or 'Latest'}",
            "formula": "(Inventories / Audited_Annual_Sales) * 365",
            "calculation_steps": f"Prior ({prior_annual_period}): {inv_days_prior:.1f}d -> Current ({latest_annual_period}): {inv_days_latest:.1f}d (Shift: {inv_days_change:+.1f} days)" if (inv_days_latest is not None and inv_days_prior is not None) else "Audited balance sheet ratios",
            "plain_english": "The average duration finished goods and raw materials sit in distribution warehouses before being sold.",
            "what_it_signifies": "Reflects working capital tied up in supply chain inventory buffers. Expansion indicates potential channel inventory buildup or raw material stockpiling."
        },
        {
            "name": "Cash Conversion Cycle (CCC)",
            "value": f"{ccc_latest:.1f} days" if ccc_latest is not None else "Data Insufficient",
            "period": f"Audited Annual: {latest_annual_period or 'Latest'}",
            "formula": "Debtor_Days + Inventory_Days - Days_Payable",
            "calculation_steps": f"{debtor_days_latest:.1f}d + {inv_days_latest:.1f}d - {payable_days_latest:.1f}d = {ccc_latest:.1f} days" if (debtor_days_latest is not None and inv_days_latest is not None and payable_days_latest is not None) else "Audited balance sheet ratios",
            "plain_english": "The net operational turnover cycle funded by corporate working capital versus vendor supplier credit.",
            "what_it_signifies": (
                f"A negative cycle ({ccc_latest:.1f} days) demonstrates that the company's suppliers are effectively funding its entire operating working capital."
                if (ccc_latest is not None and ccc_latest < 0)
                else "Measures the net time required to turn operational inventory and receivables investments into cash collections."
            )
        }
    ]

    candidate_anomalies = []

    # 1. Operating Cash Flow Conversion Decoupling (EBITDA vs CFO)
    if cfo_to_op_profit_pct is not None:
        if cfo_to_op_profit_pct < 85.0 or (prior_cfo_to_op_profit_pct and (prior_cfo_to_op_profit_pct - cfo_to_op_profit_pct) > 5.0):
            shift_from_prior = round(prior_cfo_to_op_profit_pct - cfo_to_op_profit_pct, 2) if prior_cfo_to_op_profit_pct else 0.0
            sev = min(9.5, max(5.0, round(6.5 + (shift_from_prior * 0.15), 1)))
            candidate_anomalies.append({
                "id": "anomaly_cfo_ebitda_decoupling",
                "metric": "Operating Cash Flow to EBITDA Decoupling",
                "severity": sev,
                "summary": f"Audited Cash Flow from Operations (CFO) converted at {cfo_to_op_profit_pct:.1f}% of Operating Profit (EBITDA ex-Other Income) in {latest_annual_period}, contracting from {prior_cfo_to_op_profit_pct:.1f}% in {prior_annual_period}." if prior_cfo_to_op_profit_pct else f"Audited CFO conversion stood at {cfo_to_op_profit_pct:.1f}% of Operating Profit in {latest_annual_period}.",
                "math_detail": f"FY {latest_annual_period}: Audited CFO ₹{latest_annual_cfo:,.1f} Cr / Audited Operating Profit ₹{latest_annual_op:,.1f} Cr = {cfo_to_op_profit_pct:.2f}% (vs FY {prior_annual_period}: {prior_cfo_to_op_profit_pct:.2f}%).",
                "plain_english": f"For every ₹100 of operating profit shown on statutory accrual accounts, only ₹{cfo_to_op_profit_pct:.1f} entered bank accounts as physical operational cash.",
                "significance": "A classical divergence where statutory accounting operating profits rise while cash conversion drops steadily indicates working capital absorption or extended trade credit."
            })

    # 2. Margin Squeeze & Expense Outpacing Top-Line
    if expense_growth_yoy is not None and revenue_growth_yoy is not None:
        cost_gap = round(expense_growth_yoy - revenue_growth_yoy, 2)
        if cost_gap > 0.0:
            sev = min(9.0, max(4.0, round(5.0 + (cost_gap * 1.5), 1)))
            candidate_anomalies.append({
                "id": "anomaly_cost_decoupling",
                "metric": "Operating Expense Decoupling & Margin Dilution",
                "severity": sev,
                "summary": f"Quarterly operating expenses grew {expense_growth_yoy:+.2f}% YoY in {latest_period}, outpacing net revenue growth of {revenue_growth_yoy:+.2f}% YoY by {cost_gap:.2f} percentage points.",
                "math_detail": f"Expense YoY ({expense_growth_yoy:+.2f}%) - Sales YoY ({revenue_growth_yoy:+.2f}%) = {cost_gap:+.2f} pp spread; Operating margin shifted {margin_change_pp:+.2f} pp YoY.",
                "plain_english": "The money required to produce, market, and distribute goods expanded faster than sales revenue, eroding unit profitability.",
                "significance": "Demonstrates operating leverage headwind where advertising, raw material, or supply chain costs dilute incremental profits."
            })

    # 3. Structural Inventory Days Expansion (DIO)
    if inv_days_latest is not None:
        if inv_days_change is not None and inv_days_change > 0:
            sev = min(8.5, max(4.0, round(4.5 + (inv_days_change * 0.5), 1)))
            candidate_anomalies.append({
                "id": "anomaly_inventory_expansion",
                "metric": "Inventory Holding Expansion (DIO)",
                "severity": sev,
                "summary": f"Inventory days expanded to {inv_days_latest:.1f} days in {latest_annual_period} ({inv_days_change:+.1f} days shift vs {prior_annual_period} baseline of {inv_days_prior:.1f}d).",
                "math_detail": f"Inventory Turnover Days: {inv_days_prior:.1f}d -> {inv_days_latest:.1f}d ({inv_days_change:+.1f} days).",
                "plain_english": "Finished products and input materials are sitting in warehouses longer before conversion to finished sales.",
                "significance": "Ties up physical capital in warehouses and increases vulnerability to product discounting or inventory holding costs."
            })
        elif inv_days_latest >= 60.0:
            candidate_anomalies.append({
                "id": "anomaly_inventory_holding",
                "metric": "Elevated Inventory Days Holding Baseline",
                "severity": 5.8,
                "summary": f"Inventory holding remains elevated at {inv_days_latest:.1f} days in {latest_annual_period} (vs {prior_annual_period} baseline of {inv_days_prior:.1f}d)." if inv_days_prior else f"Inventory holding remains elevated at {inv_days_latest:.1f} days in {latest_annual_period}.",
                "math_detail": f"DIO maintained at {inv_days_latest:.1f} days across audited annual statements.",
                "plain_english": "The company maintains over two months of inventory across its national distribution and factory network.",
                "significance": "Requires sustained operational working capital commitment to maintain multi-brand supply chain replenishment."
            })

    # 4. Supplier Payable Terms & Negative Working Capital Stretch
    if payable_days_latest is not None and ccc_latest is not None:
        pay_change = round(payable_days_latest - payable_days_prior, 1) if payable_days_prior else 0.0
        candidate_anomalies.append({
            "id": "anomaly_payable_stretch",
            "metric": "Supplier Payable Elongation & Working Capital Financing",
            "severity": 6.2 if pay_change > 10.0 else 5.2,
            "summary": f"Days Payable extended to {payable_days_latest:.1f} days (from {payable_days_prior:.1f}d), pushing Cash Conversion Cycle deeper to {ccc_latest:.1f} days.",
            "math_detail": f"Days Payable: {payable_days_prior:.1f}d -> {payable_days_latest:.1f}d (Delta: {pay_change:+.1f}d); CCC: {ccc_latest:.1f} days.",
            "plain_english": f"The company takes {payable_days_latest:.1f} days on average to pay its vendor suppliers, effectively using trade payables to fund negative working capital.",
            "significance": "Enables the company to cushion internal operating cash deceleration by deferring payments to supply-chain vendors."
        })

    # 5. Distributor Debtor Days (DSO) Dynamic
    if debtor_days_latest is not None and debtor_days_prior is not None:
        sev = 5.0 if abs(debtor_days_change) > 3.0 else 4.2
        candidate_anomalies.append({
            "id": "anomaly_debtor_days_shift",
            "metric": "Distributor Credit Velocity (Debtor Days)",
            "severity": sev,
            "summary": f"Distributor debtor days settled at {debtor_days_latest:.1f} days in {latest_annual_period} ({debtor_days_change:+.1f} days vs {debtor_days_prior:.1f}d in {prior_annual_period}).",
            "math_detail": f"Trade Debtor Days: {debtor_days_prior:.1f}d -> {debtor_days_latest:.1f}d (Shift: {debtor_days_change:+.1f} days).",
            "plain_english": f"Wholesale distributors and organized retail partners take an average of {debtor_days_latest:.1f} days to settle invoices.",
            "significance": "Audits distributor channel financing exposure and credit terms extended to traditional and modern trade partners."
        })

    # Sort strictly descending by severity score
    candidate_anomalies.sort(key=lambda x: x.get("severity", 0.0), reverse=True)
    top_5_anomalies = candidate_anomalies[:5]

    return {
        "ticker": ticker,
        "company_name": company_name,
        "latest_period": latest_period,
        "prior_yoy_period": prior_yoy_period,
        "latest_annual_period": latest_annual_period,
        "prior_annual_period": prior_annual_period,
        "revenue_growth_yoy": revenue_growth_yoy,
        "operating_margin": current_margin,
        "margin_change_pp": margin_change_pp,
        "expense_growth_yoy": expense_growth_yoy,
        "debtor_days_latest": debtor_days_latest,
        "debtor_days_prior": debtor_days_prior,
        "debtor_days_change": debtor_days_change,
        "inventory_days_latest": inv_days_latest,
        "inventory_days_change": inv_days_change,
        "working_capital_days_latest": wc_days_latest,
        "working_capital_days_change": wc_days_change,
        "cfo_to_op_profit_pct": cfo_to_op_profit_pct,
        "latest_annual_cfo": latest_annual_cfo,
        "latest_annual_op": latest_annual_op,
        "key_numbers": key_numbers,
        "red_flags": top_5_anomalies,
        "anomalies": top_5_anomalies,
        "quarterly_history": quarterly_history
    }
