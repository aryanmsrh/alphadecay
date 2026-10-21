from typing import Any, Dict, List, Optional
from analytics.tools import (
    calculate_operating_margin,
    calculate_percentage_growth,
    coerce_float,
    find_yoy_prior_period,
    get_row_series,
)


def calculate_financial_indicators(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    ticker = raw_data.get("ticker", "").upper().strip()
    company_name = raw_data.get("company_name", ticker)
    quarters = raw_data.get("quarters") or raw_data.get("quarterly_results") or {}
    periods = quarters.get("periods", [])
    rows = quarters.get("rows", {})

    sales_series = get_row_series(rows, ["Sales", "Revenue", "Net Sales"])
    expenses_series = get_row_series(rows, ["Expenses", "Total Expenses"])
    op_series = get_row_series(rows, ["Operating Profit", "Financing Profit", "EBITDA"])
    opm_series = get_row_series(rows, ["OPM %", "Financing Margin %"])

    sales_by_p, exp_by_p, op_by_p, opm_by_p = {}, {}, {}, {}
    for idx, p in enumerate(periods):
        if idx < len(sales_series) and (v := coerce_float(sales_series[idx])) is not None:
            sales_by_p[p] = v
        if idx < len(expenses_series) and (v := coerce_float(expenses_series[idx])) is not None:
            exp_by_p[p] = v
        if idx < len(op_series) and (v := coerce_float(op_series[idx])) is not None:
            op_by_p[p] = v
        if idx < len(opm_series) and (v := coerce_float(opm_series[idx])) is not None:
            opm_by_p[p] = v

    quarterly_history = []
    for p in (periods[-8:] if len(periods) >= 8 else periods):
        rev, op, margin = sales_by_p.get(p), op_by_p.get(p), opm_by_p.get(p)
        if margin is None and rev and op is not None:
            margin = calculate_operating_margin(op, rev)
        quarterly_history.append({"period": p, "revenue": rev, "expenses": exp_by_p.get(p), "operating_profit": op, "operating_margin_pct": margin})

    latest_period = periods[-1] if periods else "Latest"
    prior_yoy_period = find_yoy_prior_period(latest_period, periods)
    current_sales, prior_sales = sales_by_p.get(latest_period), (sales_by_p.get(prior_yoy_period) if prior_yoy_period else None)
    revenue_growth_yoy = calculate_percentage_growth(current_sales, prior_sales)

    current_expenses, prior_expenses = exp_by_p.get(latest_period), (exp_by_p.get(prior_yoy_period) if prior_yoy_period else None)
    expense_growth_yoy = calculate_percentage_growth(current_expenses, prior_expenses)

    current_op = op_by_p.get(latest_period)
    current_margin = calculate_operating_margin(current_op, current_sales)
    prior_op = op_by_p.get(prior_yoy_period) if prior_yoy_period else None
    prior_margin = calculate_operating_margin(prior_op, prior_sales)
    margin_change_pp = round(current_margin - prior_margin, 2) if (current_margin is not None and prior_margin is not None) else None

    # Annual Statements & Cash Flows
    pl_data = raw_data.get("profit_loss") or raw_data.get("annual_pnl") or {}
    pl_periods = pl_data.get("periods", [])
    pl_op_series = get_row_series(pl_data.get("rows", {}), ["Operating Profit", "Financing Profit", "EBITDA"])
    cf_data = raw_data.get("cash_flow") or raw_data.get("cashflow") or {}
    cf_periods = cf_data.get("periods", [])
    cfo_series = get_row_series(cf_data.get("rows", {}), ["Cash from Operating Activity", "Operating Cash Flow"])

    pl_op_by_period = {p: coerce_float(pl_op_series[i]) for i, p in enumerate(pl_periods) if p != "TTM" and i < len(pl_op_series) and coerce_float(pl_op_series[i]) is not None}
    cfo_by_period = {p: coerce_float(cfo_series[i]) for i, p in enumerate(cf_periods) if i < len(cfo_series) and coerce_float(cfo_series[i]) is not None}

    common_annual = [p for p in cf_periods if p in pl_op_by_period and p in cfo_by_period]
    latest_annual = common_annual[-1] if common_annual else None
    prior_annual = common_annual[-2] if len(common_annual) >= 2 else None

    latest_annual_cfo, latest_annual_op = cfo_by_period.get(latest_annual), pl_op_by_period.get(latest_annual)
    prior_annual_cfo, prior_annual_op = cfo_by_period.get(prior_annual), pl_op_by_period.get(prior_annual)

    cfo_to_op_profit_pct = round((latest_annual_cfo / latest_annual_op) * 100.0, 2) if (latest_annual_cfo is not None and latest_annual_op and latest_annual_op > 0) else None
    prior_cfo_to_op_profit_pct = round((prior_annual_cfo / prior_annual_op) * 100.0, 2) if (prior_annual_cfo is not None and prior_annual_op and prior_annual_op > 0) else None
    cfo_conversion_delta_pp = round(cfo_to_op_profit_pct - prior_cfo_to_op_profit_pct, 2) if (cfo_to_op_profit_pct is not None and prior_cfo_to_op_profit_pct is not None) else None

    # Working Capital Ratios
    ratios_rows = (raw_data.get("ratios_table") or raw_data.get("ratios") or {}).get("rows", {})
    def _clean_ratios(keys):
        return [v for v in (coerce_float(x) for x in get_row_series(ratios_rows, keys)) if v is not None]

    dio_s = _clean_ratios(["Inventory Days", "InventoryDays", "DIO"])
    inv_days_latest, inv_days_prior = (dio_s[-1] if dio_s else None), (dio_s[-2] if len(dio_s) >= 2 else None)
    inv_days_change = round(inv_days_latest - inv_days_prior, 1) if (inv_days_latest is not None and inv_days_prior is not None) else None

    dso_s = _clean_ratios(["Debtor Days", "DebtorDays", "DSO"])
    debtor_days_latest, debtor_days_prior = (dso_s[-1] if dso_s else None), (dso_s[-2] if len(dso_s) >= 2 else None)
    debtor_days_change = round(debtor_days_latest - debtor_days_prior, 1) if (debtor_days_latest is not None and debtor_days_prior is not None) else None

    dpo_s = _clean_ratios(["Days Payable", "DaysPayable", "DPO"])
    payable_days_latest, payable_days_prior = (dpo_s[-1] if dpo_s else None), (dpo_s[-2] if len(dpo_s) >= 2 else None)
    payable_days_change = round(payable_days_latest - payable_days_prior, 1) if (payable_days_latest is not None and payable_days_prior is not None) else None

    ccc_s = _clean_ratios(["Cash Conversion Cycle", "CashConversionCycle", "CCC"])
    ccc_latest, ccc_prior = (ccc_s[-1] if ccc_s else None), (ccc_s[-2] if len(ccc_s) >= 2 else None)
    ccc_change = round(ccc_latest - ccc_prior, 1) if (ccc_latest is not None and ccc_prior is not None) else None

    ann_period_str = f"Audited Annual: {latest_annual or 'Latest'}"
    q_period_str = f"Quarterly: {latest_period} vs {prior_yoy_period}" if prior_yoy_period else f"Quarterly: {latest_period}"
    key_numbers = [
        {"name": "Revenue Growth (YoY)", "value": f"{revenue_growth_yoy:+.2f}%" if revenue_growth_yoy is not None else "N/A", "period": q_period_str},
        {"name": "Operating Profit (EBITDA ex-Other Income) Margin", "value": f"{current_margin:.2f}%" if current_margin is not None else "N/A", "period": f"Quarterly: {latest_period}"},
        {"name": "Operating Margin YoY Spread", "value": f"{margin_change_pp:+.2f} pp" if margin_change_pp is not None else "N/A", "period": q_period_str},
        {"name": "Operating Expense Growth (YoY)", "value": f"{expense_growth_yoy:+.2f}%" if expense_growth_yoy is not None else "N/A", "period": q_period_str},
        {"name": "Operating Cash Flow (CFO) to EBITDA Conversion", "value": f"{cfo_to_op_profit_pct:.2f}%" if cfo_to_op_profit_pct is not None else "N/A", "period": ann_period_str},
        {"name": "Trade Receivables / Debtor Days (DSO)", "value": f"{debtor_days_latest:.1f} days" if debtor_days_latest is not None else "N/A", "period": ann_period_str},
        {"name": "Days Inventory Outstanding (DIO)", "value": f"{inv_days_latest:.1f} days" if inv_days_latest is not None else "N/A", "period": ann_period_str},
        {"name": "Days Payable Outstanding (DPO)", "value": f"{payable_days_latest:.1f} days" if payable_days_latest is not None else "N/A", "period": ann_period_str},
        {"name": "Cash Conversion Cycle (CCC)", "value": f"{ccc_latest:.1f} days" if ccc_latest is not None else "N/A", "period": ann_period_str},
    ]

    candidate_anomalies = []

    # 1. CFO / EBITDA Conversion
    if cfo_to_op_profit_pct is not None:
        cfo_delta = cfo_conversion_delta_pp or 0.0
        if cfo_to_op_profit_pct < 80.0 or cfo_delta < 0:
            sev = round(min(9.2, max(6.0, 6.0 + abs(cfo_delta) * 0.15 + (1.5 if cfo_to_op_profit_pct < 80.0 else 0.0))), 1)
        else:
            sev = round(max(2.5, min(4.5, 4.2 - (0.5 if cfo_to_op_profit_pct >= 90.0 else 0.0))), 1)

        cfo_traj = [f"{p}: CFO ₹{cfo_by_period[p]:,.1f} Cr / EBITDA ₹{pl_op_by_period[p]:,.1f} Cr ({(cfo_by_period[p]/pl_op_by_period[p])*100.0:.1f}%)" for p in common_annual[-4:] if pl_op_by_period.get(p, 0) > 0 and cfo_by_period.get(p) is not None]
        cfo_traj_str = " -> ".join(cfo_traj) if cfo_traj else f"{prior_annual or 'Prior'} -> {latest_annual or 'Latest'}"
        candidate_anomalies.append({
            "id": "signal_cfo_ebitda",
            "metric": "Operating Cash Flow to EBITDA Conversion",
            "severity": sev,
            "multi_quarter_trajectory": cfo_traj_str,
            "numbers_bullets": [
                f"Operating Cash Flow (CFO): ₹{prior_annual_cfo:,.1f} Cr ({prior_annual}) -> ₹{latest_annual_cfo:,.1f} Cr ({latest_annual})" if (prior_annual_cfo and latest_annual_cfo) else f"Operating Cash Flow (CFO): ₹{latest_annual_cfo:,.1f} Cr",
                f"Operating Profit (EBITDA): ₹{prior_annual_op:,.1f} Cr ({prior_annual}) -> ₹{latest_annual_op:,.1f} Cr ({latest_annual})" if (prior_annual_op and latest_annual_op) else f"Operating Profit (EBITDA): ₹{latest_annual_op:,.1f} Cr",
                f"CFO to EBITDA Conversion Rate: {prior_cfo_to_op_profit_pct:.2f}% ({prior_annual}) -> {cfo_to_op_profit_pct:.2f}% ({latest_annual}) ({cfo_delta:+.2f} pp YoY)" if prior_cfo_to_op_profit_pct is not None else f"CFO to EBITDA Conversion Rate: {cfo_to_op_profit_pct:.2f}%",
                f"Historical Conversion Trajectory: {cfo_traj_str}",
            ],
        })

    # 2. Expense Wedge & Margin Trajectory
    if expense_growth_yoy is not None and revenue_growth_yoy is not None:
        cost_wedge = round(expense_growth_yoy - revenue_growth_yoy, 2)
        if cost_wedge > 0 or (margin_change_pp is not None and margin_change_pp < 0):
            sev = round(min(9.2, max(6.5, 6.0 + max(0.0, cost_wedge) * 0.35 + (abs(margin_change_pp) * 0.35 if (margin_change_pp and margin_change_pp < 0) else 0.0))), 1)
        else:
            sev = round(max(2.5, min(4.5, 4.2 - abs(cost_wedge) * 0.1)), 1)

        q_traj = [f"{q['period']}: Sales ₹{q['revenue']:,.1f} Cr | OPM {q['operating_margin_pct']:.2f}%" for q in quarterly_history if q.get("revenue") is not None and q.get("operating_margin_pct") is not None]
        q_traj_str = " -> ".join(q_traj) if q_traj else f"{prior_yoy_period or 'Prior'} -> {latest_period or 'Latest'}"
        candidate_anomalies.append({
            "id": "signal_margin_cost_dynamics",
            "metric": "Revenue vs Operating Expense & Margin Trajectory",
            "severity": sev,
            "multi_quarter_trajectory": q_traj_str,
            "numbers_bullets": [
                f"Net Sales (Quarter Ended {latest_period} vs YoY Baseline {prior_yoy_period}): ₹{prior_sales:,.1f} Cr ({prior_yoy_period}) -> ₹{current_sales:,.1f} Cr ({latest_period}) ({revenue_growth_yoy:+.2f}% YoY)" if (prior_sales and current_sales) else f"Net Sales: ₹{current_sales:,.1f} Cr",
                f"Operating Expenses (Quarter Ended {latest_period} vs YoY Baseline {prior_yoy_period}): ₹{prior_expenses:,.1f} Cr ({prior_yoy_period}) -> ₹{current_expenses:,.1f} Cr ({latest_period}) ({expense_growth_yoy:+.2f}% YoY)" if (prior_expenses and current_expenses) else f"Operating Expenses: ₹{current_expenses:,.1f} Cr",
                f"Expense-to-Sales Wedge: {cost_wedge:+.2f} pp ({expense_growth_yoy:+.2f}% expenses vs {revenue_growth_yoy:+.2f}% sales)",
                f"Operating Profit Margin: {prior_margin:.2f}% -> {current_margin:.2f}% ({margin_change_pp:+.2f} pp / {int(margin_change_pp * 100):+d} bps)" if (prior_margin is not None and current_margin is not None and margin_change_pp is not None) else f"Operating Profit Margin: {current_margin:.2f}%",
                f"Operating Profit (EBITDA ex-Other Income): ₹{prior_op:,.1f} Cr -> ₹{current_op:,.1f} Cr" if (prior_op and current_op) else f"Operating Profit: ₹{current_op:,.1f} Cr",
                f"Quarterly Trajectory: {q_traj_str}",
            ],
        })

    # 3. Inventory Velocity (DIO)
    if inv_days_latest is not None and inv_days_prior is not None:
        inv_delta = inv_days_change or 0.0
        sev = round(min(9.0, max(6.0, 6.0 + max(0.0, inv_delta) * 0.2 + (max(0.0, inv_days_latest - 75.0) * 0.05))) if (inv_delta > 0 or inv_days_latest > 75.0) else max(2.5, min(4.5, 4.2 - abs(inv_delta) * 0.1)), 1)
        dio_traj_str = " -> ".join([f"{v:.1f}d" for v in dio_s[-5:]]) if dio_s else f"{inv_days_prior:.1f}d -> {inv_days_latest:.1f}d"
        candidate_anomalies.append({
            "id": "signal_inventory_dio",
            "metric": "Inventory Holding Velocity (DIO)",
            "severity": sev,
            "multi_quarter_trajectory": dio_traj_str,
            "numbers_bullets": [
                f"Days Inventory Outstanding (DIO): {inv_days_prior:.1f} days ({prior_annual}) -> {inv_days_latest:.1f} days ({latest_annual}) ({inv_delta:+.1f} days YoY)",
                f"Multi-Year DIO Trajectory: {dio_traj_str}",
            ],
        })

    # 4. Supplier Payable (DPO) & Cash Conversion Cycle (CCC)
    if payable_days_latest is not None and payable_days_prior is not None:
        pay_delta = payable_days_change or 0.0
        sev = round(min(8.8, max(5.8, 5.5 + abs(pay_delta) * 0.15 + (max(0.0, ccc_change or 0.0) * 0.15))) if (pay_delta < 0 or (ccc_change is not None and ccc_change > 0)) else max(2.5, min(4.5, 4.0)), 1)
        pay_traj_str = " -> ".join([f"CCC {v:.1f}d" for v in ccc_s[-5:]]) if ccc_s else f"{prior_annual} -> {latest_annual}"
        pay_bullets = [f"Days Payable Outstanding (DPO): {payable_days_prior:.1f} days ({prior_annual}) -> {payable_days_latest:.1f} days ({latest_annual}) ({pay_delta:+.1f} days YoY)"]
        if ccc_latest is not None and ccc_prior is not None:
            pay_bullets.append(f"Cash Conversion Cycle (CCC): {ccc_prior:.1f} days ({prior_annual}) -> {ccc_latest:.1f} days ({latest_annual}) ({ccc_change:+.1f} days YoY)")
        if debtor_days_latest is not None and inv_days_latest is not None and payable_days_latest is not None and ccc_latest is not None:
            pay_bullets.append(f"Working Capital Formula: {debtor_days_latest:.1f}d DSO + {inv_days_latest:.1f}d DIO - {payable_days_latest:.1f}d DPO = {ccc_latest:.1f}d CCC")
        pay_bullets.append(f"Multi-Year Working Capital Trajectory: {pay_traj_str}")
        candidate_anomalies.append({
            "id": "signal_payables_ccc",
            "metric": "Supplier Payable Terms (DPO) & Cash Conversion Cycle (CCC)",
            "severity": sev,
            "multi_quarter_trajectory": pay_traj_str,
            "numbers_bullets": pay_bullets,
        })

    # 5. Distributor & Channel Credit Velocity (DSO)
    if debtor_days_latest is not None and debtor_days_prior is not None:
        deb_delta = debtor_days_change or 0.0
        sev = round(min(9.0, max(6.0, 6.0 + max(0.0, deb_delta) * 0.3 + (max(0.0, debtor_days_latest - 25.0) * 0.08))) if (deb_delta > 0 or debtor_days_latest > 25.0) else max(2.5, min(4.5, 4.2 - abs(deb_delta) * 0.1)), 1)
        dso_traj_str = " -> ".join([f"{v:.1f}d" for v in dso_s[-5:]]) if dso_s else f"{debtor_days_prior:.1f}d -> {debtor_days_latest:.1f}d"
        candidate_anomalies.append({
            "id": "signal_debtor_days",
            "metric": "Distributor & Channel Credit Velocity (Debtor Days / DSO)",
            "severity": sev,
            "multi_quarter_trajectory": dso_traj_str,
            "numbers_bullets": [
                f"Trade Debtor Days (DSO): {debtor_days_prior:.1f} days ({prior_annual}) -> {debtor_days_latest:.1f} days ({latest_annual}) ({deb_delta:+.1f} days YoY)",
                f"Multi-Year DSO Trajectory: {dso_traj_str}",
            ],
        })

    candidate_anomalies.sort(key=lambda x: x.get("severity", 0.0), reverse=True)
    top_5_anomalies = candidate_anomalies[:5]

    return {
        "ticker": ticker,
        "company_name": company_name,
        "latest_period": latest_period,
        "prior_yoy_period": prior_yoy_period,
        "revenue_growth_yoy": revenue_growth_yoy,
        "operating_margin": current_margin,
        "margin_change_pp": margin_change_pp,
        "expense_growth_yoy": expense_growth_yoy,
        "cfo_to_op_profit_pct": cfo_to_op_profit_pct,
        "debtor_days_latest": debtor_days_latest,
        "inventory_days_latest": inv_days_latest,
        "key_numbers": key_numbers,
        "anomalies": top_5_anomalies,
        "quarterly_history": quarterly_history,
    }
