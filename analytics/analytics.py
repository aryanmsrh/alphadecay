from typing import Any, Dict, List, Optional, Tuple
from analytics.tools import (
    MONTH_NAMES,
    parse_period_key,
    find_yoy_prior_period,
    calculate_percentage_growth,
    calculate_operating_margin,
    coerce_float,
    normalize_row_key,
    _normalize_row_key,
    get_row_series,
    _get_row_series,
    safe_fmt,
)


def calculate_financial_indicators(raw_data: Dict[str, Any], peer_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
  ticker = raw_data.get("ticker", "").upper().strip()
  company_name = raw_data.get("company_name", ticker)
  quarters = raw_data.get("quarters") or raw_data.get("quarterly_results") or {}
  periods = quarters.get("periods", [])
  rows = quarters.get("rows", {})

  sales_series = _get_row_series(rows, ["Sales", "Revenue", "Net Sales"])
  expenses_series = _get_row_series(rows, ["Expenses", "Total Expenses"])
  operating_profit_series = _get_row_series(
      rows, ["Operating Profit", "Financing Profit", "EBITDA"]
  )
  opm_series = _get_row_series(rows, ["OPM %", "Financing Margin %"])

  sales_by_period = {}
  expenses_by_period = {}
  operating_profit_by_period = {}
  opm_by_period = {}

  for idx, p in enumerate(periods):
    if idx < len(sales_series):
      val = coerce_float(sales_series[idx])
      if val is not None:
        sales_by_period[p] = val
    if idx < len(expenses_series):
      val = coerce_float(expenses_series[idx])
      if val is not None:
        expenses_by_period[p] = val
    if idx < len(operating_profit_series):
      val = coerce_float(operating_profit_series[idx])
      if val is not None:
        operating_profit_by_period[p] = val
    if idx < len(opm_series):
      val = coerce_float(opm_series[idx])
      if val is not None:
        opm_by_period[p] = val

  quarterly_history = []
  trailing_periods = periods[-8:] if len(periods) >= 8 else periods

  for p in trailing_periods:
    rev = sales_by_period.get(p)
    exp = expenses_by_period.get(p)
    op = operating_profit_by_period.get(p)
    margin = opm_by_period.get(p)
    if margin is None and rev and op is not None:
      margin = calculate_operating_margin(op, rev)

    quarterly_history.append({
        "period": p,
        "revenue": rev,
        "expenses": exp,
        "operating_profit": op,
        "operating_margin_pct": margin,
    })

  latest_period = periods[-1] if periods else "Latest"
  prior_yoy_period = find_yoy_prior_period(latest_period, periods)

  current_sales = sales_by_period.get(latest_period)
  prior_sales = (
      sales_by_period.get(prior_yoy_period) if prior_yoy_period else None
  )
  revenue_growth_yoy = calculate_percentage_growth(current_sales, prior_sales)

  current_expenses = expenses_by_period.get(latest_period)
  prior_expenses = (
      expenses_by_period.get(prior_yoy_period) if prior_yoy_period else None
  )
  expense_growth_yoy = calculate_percentage_growth(
      current_expenses, prior_expenses
  )

  current_op = operating_profit_by_period.get(latest_period)
  current_margin = calculate_operating_margin(current_op, current_sales)
  prior_op = (
      operating_profit_by_period.get(prior_yoy_period)
      if prior_yoy_period
      else None
  )
  prior_margin = calculate_operating_margin(prior_op, prior_sales)

  margin_change_pp = None
  if current_margin is not None and prior_margin is not None:
    margin_change_pp = round(current_margin - prior_margin, 2)

  pl_data = raw_data.get("profit_loss") or raw_data.get("annual_pnl") or {}
  pl_periods = pl_data.get("periods", [])
  pl_rows = pl_data.get("rows", {})
  pl_sales = _get_row_series(pl_rows, ["Sales", "Revenue", "Net Sales"])
  pl_op = _get_row_series(
      pl_rows, ["Operating Profit", "Financing Profit", "EBITDA"]
  )

  cf_data = raw_data.get("cash_flow") or raw_data.get("cashflow") or {}
  cf_periods = cf_data.get("periods", [])
  cf_rows = cf_data.get("rows", {})
  cfo_series_raw = _get_row_series(
      cf_rows, ["Cash from Operating Activity", "Operating Cash Flow"]
  )

  pl_op_by_period = {}
  pl_sales_by_period = {}
  for idx, p in enumerate(pl_periods):
    if p != "TTM":
      if idx < len(pl_op):
        val = coerce_float(pl_op[idx])
        if val is not None:
          pl_op_by_period[p] = val
      if idx < len(pl_sales):
        val = coerce_float(pl_sales[idx])
        if val is not None:
          pl_sales_by_period[p] = val

  cfo_by_period = {}
  for idx, p in enumerate(cf_periods):
    if idx < len(cfo_series_raw):
      val = coerce_float(cfo_series_raw[idx])
      if val is not None:
        cfo_by_period[p] = val

  common_annual_periods = [
      p for p in cf_periods if p in pl_op_by_period and p in cfo_by_period
  ]
  latest_annual_period = (
      common_annual_periods[-1] if common_annual_periods else None
  )
  prior_annual_period = (
      common_annual_periods[-2] if len(common_annual_periods) >= 2 else None
  )

  latest_annual_cfo = (
      cfo_by_period.get(latest_annual_period) if latest_annual_period else None
  )
  latest_annual_op = (
      pl_op_by_period.get(latest_annual_period)
      if latest_annual_period
      else None
  )
  cfo_to_op_profit_pct = None
  if (
      latest_annual_cfo is not None
      and latest_annual_op
      and latest_annual_op > 0
  ):
    cfo_to_op_profit_pct = round(
        (latest_annual_cfo / latest_annual_op) * 100.0, 2
    )

  prior_annual_cfo = (
      cfo_by_period.get(prior_annual_period) if prior_annual_period else None
  )
  prior_annual_op = (
      pl_op_by_period.get(prior_annual_period) if prior_annual_period else None
  )
  prior_cfo_to_op_profit_pct = None
  if prior_annual_cfo is not None and prior_annual_op and prior_annual_op > 0:
    prior_cfo_to_op_profit_pct = round(
        (prior_annual_cfo / prior_annual_op) * 100.0, 2
    )

  cfo_conversion_delta_pp = None
  if cfo_to_op_profit_pct is not None and prior_cfo_to_op_profit_pct is not None:
    cfo_conversion_delta_pp = round(
        cfo_to_op_profit_pct - prior_cfo_to_op_profit_pct, 2
    )

  ratios_table = raw_data.get("ratios_table") or raw_data.get("ratios") or {}
  ratios_rows = ratios_table.get("rows", {})

  clean_debtor_days = [
      coerce_float(v)
      for v in _get_row_series(ratios_rows, ["Debtor Days", "DebtorDays", "DSO"])
      if coerce_float(v) is not None
  ]
  debtor_days_latest = clean_debtor_days[-1] if clean_debtor_days else None
  debtor_days_prior = (
      clean_debtor_days[-2] if len(clean_debtor_days) >= 2 else None
  )
  debtor_days_change = (
      round(debtor_days_latest - debtor_days_prior, 1)
      if (debtor_days_latest is not None and debtor_days_prior is not None)
      else None
  )

  clean_inv_days = [
      coerce_float(v)
      for v in _get_row_series(ratios_rows, ["Inventory Days", "InventoryDays", "DIO"])
      if coerce_float(v) is not None
  ]
  inv_days_latest = clean_inv_days[-1] if clean_inv_days else None
  inv_days_prior = clean_inv_days[-2] if len(clean_inv_days) >= 2 else None
  inv_days_change = (
      round(inv_days_latest - inv_days_prior, 1)
      if (inv_days_latest is not None and inv_days_prior is not None)
      else None
  )

  clean_payable_days = [
      coerce_float(v)
      for v in _get_row_series(ratios_rows, ["Days Payable", "DaysPayable", "DPO"])
      if coerce_float(v) is not None
  ]
  payable_days_latest = clean_payable_days[-1] if clean_payable_days else None
  payable_days_prior = (
      clean_payable_days[-2] if len(clean_payable_days) >= 2 else None
  )
  payable_days_change = (
      round(payable_days_latest - payable_days_prior, 1)
      if (payable_days_latest is not None and payable_days_prior is not None)
      else None
  )

  clean_ccc = [
      coerce_float(v)
      for v in _get_row_series(ratios_rows, ["Cash Conversion Cycle", "CashConversionCycle", "CCC"])
      if coerce_float(v) is not None
  ]
  ccc_latest = clean_ccc[-1] if clean_ccc else None
  ccc_prior = clean_ccc[-2] if len(clean_ccc) >= 2 else None
  ccc_change = (
      round(ccc_latest - ccc_prior, 1)
      if (ccc_latest is not None and ccc_prior is not None)
      else None
  )

  clean_wc_days = [
      coerce_float(v)
      for v in _get_row_series(ratios_rows, ["Working Capital Days", "WorkingCapitalDays", "WC Days"])
      if coerce_float(v) is not None
  ]
  wc_days_latest = clean_wc_days[-1] if clean_wc_days else None
  wc_days_prior = clean_wc_days[-2] if len(clean_wc_days) >= 2 else None
  wc_days_change = (
      round(wc_days_latest - wc_days_prior, 1)
      if (wc_days_latest is not None and wc_days_prior is not None)
      else None
  )

  cf_period_label = (
      f"{latest_annual_period} vs {prior_annual_period}"
      if (latest_annual_period and prior_annual_period)
      else (latest_annual_period or "Annual Audited")
  )

  key_numbers = [
      {
          "name": "Revenue Growth (YoY)",
          "value": (
              f"{revenue_growth_yoy:+.2f}%"
              if revenue_growth_yoy is not None
              else "N/A"
          ),
          "period": (
              f"Quarterly: {latest_period} vs {prior_yoy_period}"
              if prior_yoy_period
              else latest_period
          ),
          "formula": (
              "((Net_Sales_t - Net_Sales_t_minus_4) / Net_Sales_t_minus_4)"
              " * 100"
          ),
          "calculation_steps": (
              f"(({current_sales:,.1f} Cr - {prior_sales:,.1f} Cr) /"
              f" {prior_sales:,.1f} Cr) * 100 = {revenue_growth_yoy:+.2f}%"
              if (current_sales is not None and prior_sales)
              else "N/A"
          ),
          "directional_comparison": (
              (
                  f"Net sales expanded by +{revenue_growth_yoy:.2f}% YoY"
                  + (f" (from ₹{prior_sales:,.1f} Cr to ₹{current_sales:,.1f} Cr)." if (prior_sales and current_sales) else ".")
              )
              if (revenue_growth_yoy is not None and revenue_growth_yoy > 0)
              else (
                  (
                      f"Net sales contracted by {abs(revenue_growth_yoy):.2f}% YoY"
                      + (f" (from ₹{prior_sales:,.1f} Cr down to ₹{current_sales:,.1f} Cr)." if (prior_sales and current_sales) else ".")
                  )
                  if (revenue_growth_yoy is not None and revenue_growth_yoy < 0)
                  else (
                      "Net sales remained flat YoY."
                      if revenue_growth_yoy == 0
                      else "Net sales YoY data not available."
                  )
              )
          ),
      },
      {
          "name": "Operating Profit (EBITDA ex-Other Income) Margin",
          "value": (
              f"{current_margin:.2f}%" if current_margin is not None else "N/A"
          ),
          "period": f"Quarterly: {latest_period}",
          "formula": "(Operating_Profit_ex_Other_Income / Net_Sales) * 100",
          "calculation_steps": (
              f"({current_op:,.1f} Cr / {current_sales:,.1f} Cr) * 100 ="
              f" {current_margin:.2f}%"
              if (current_op is not None and current_sales)
              else "N/A"
          ),
          "directional_comparison": (
              (
                  f"Operating profit margin stands at {current_margin:.2f}%"
                  + (f" (₹{current_op:,.1f} Cr EBITDA on ₹{current_sales:,.1f} Cr sales)." if (current_op and current_sales) else ".")
              )
              if current_margin is not None
              else "Operating profit margin not available."
          ),
      },
      {
          "name": "Operating Margin YoY Spread",
          "value": (
              f"{margin_change_pp:+.2f} pp ({int(margin_change_pp * 100):+d}"
              " bps)"
              if margin_change_pp is not None
              else "N/A"
          ),
          "period": (
              f"Quarterly: {latest_period} vs {prior_yoy_period}"
              if prior_yoy_period
              else latest_period
          ),
          "formula": "Current_OPM - Prior_YoY_OPM",
          "calculation_steps": (
              f"{current_margin:.2f}% - {prior_margin:.2f}% ="
              f" {margin_change_pp:+.2f} pp ({int(margin_change_pp * 100):+d}"
              " bps)"
              if (current_margin is not None and prior_margin is not None)
              else "N/A"
          ),
          "directional_comparison": (
              (
                  f"Operating margin expanded by +{margin_change_pp:.2f} pp (+{int(margin_change_pp * 100)} bps) from {prior_margin:.2f}% to {current_margin:.2f}%."
                  if (margin_change_pp > 0 and prior_margin is not None and current_margin is not None)
                  else (
                      f"Operating margin contracted by {abs(margin_change_pp):.2f} pp ({int(margin_change_pp * 100)} bps) from {prior_margin:.2f}% down to {current_margin:.2f}%."
                      if (margin_change_pp < 0 and prior_margin is not None and current_margin is not None)
                      else (
                          f"Operating margin remained flat at {current_margin:.2f}%."
                          if (margin_change_pp == 0 and current_margin is not None)
                          else (
                              f"Operating margin stands at {current_margin:.2f}%."
                              if current_margin is not None
                              else "Operating margin spread not available."
                          )
                      )
                  )
              )
              if margin_change_pp is not None
              else "Operating margin spread not available."
          ),
      },
      {
          "name": "Operating Expense Growth (YoY)",
          "value": (
              f"{expense_growth_yoy:+.2f}%"
              if expense_growth_yoy is not None
              else "N/A"
          ),
          "period": (
              f"Quarterly: {latest_period} vs {prior_yoy_period}"
              if prior_yoy_period
              else latest_period
          ),
          "formula": (
              "((Operating_Expenses_t - Operating_Expenses_t_minus_4) /"
              " Operating_Expenses_t_minus_4) * 100"
          ),
          "calculation_steps": (
              f"(({current_expenses:,.1f} Cr - {prior_expenses:,.1f} Cr) /"
              f" {prior_expenses:,.1f} Cr) * 100 = {expense_growth_yoy:+.2f}%"
              if (current_expenses is not None and prior_expenses)
              else "N/A"
          ),
          "directional_comparison": (
              (
                  f"Operating expenses grew by {expense_growth_yoy:+.2f}% YoY vs Net Sales growth of {revenue_growth_yoy:+.2f}% YoY "
                  + (
                      f"(Operating costs outgrew net sales by {expense_growth_yoy - revenue_growth_yoy:+.2f} pp)."
                      if expense_growth_yoy > revenue_growth_yoy
                      else (
                          f"(Net sales outgrew operating costs by {revenue_growth_yoy - expense_growth_yoy:+.2f} pp)."
                          if revenue_growth_yoy > expense_growth_yoy
                          else "(Sales and expenses grew at parity)."
                      )
                  )
              )
              if (expense_growth_yoy is not None and revenue_growth_yoy is not None)
              else (
                  f"Operating expenses grew by {expense_growth_yoy:+.2f}% YoY."
                  if expense_growth_yoy is not None
                  else "Operating expense growth not available."
              )
          ),
      },
      {
          "name": "Operating Cash Flow (CFO) to EBITDA Conversion",
          "value": (
              f"{cfo_to_op_profit_pct:.2f}% of EBITDA"
              if cfo_to_op_profit_pct is not None
              else "N/A"
          ),
          "period": f"Audited Annual: {cf_period_label}",
          "formula": (
              "(Audited_Annual_CFO / Audited_Annual_Operating_Profit_EBITDA)"
              " * 100"
          ),
          "calculation_steps": (
              f"({latest_annual_cfo:,.1f} Cr / {latest_annual_op:,.1f} Cr) *"
              f" 100 = {cfo_to_op_profit_pct:.2f}%"
              + (
                  f" (Prior {prior_annual_period}: {prior_cfo_to_op_profit_pct:.2f}% | Change: {cfo_conversion_delta_pp:+.2f} pp)"
                  if (prior_cfo_to_op_profit_pct is not None and cfo_conversion_delta_pp is not None)
                  else ""
              )
              if (
                  latest_annual_cfo is not None
                  and latest_annual_op
                  and cfo_to_op_profit_pct is not None
              )
              else "N/A"
          ),
          "directional_comparison": (
              (
                  (
                      f"Operating cash flow conversion expanded by +{cfo_conversion_delta_pp:.2f} pp from {prior_cfo_to_op_profit_pct:.2f}% in {prior_annual_period} to {cfo_to_op_profit_pct:.2f}% in {latest_annual_period}."
                      if (cfo_conversion_delta_pp is not None and cfo_conversion_delta_pp > 0 and prior_cfo_to_op_profit_pct is not None)
                      else (
                          f"Operating cash flow conversion contracted by {abs(cfo_conversion_delta_pp):.2f} pp from {prior_cfo_to_op_profit_pct:.2f}% in {prior_annual_period} down to {cfo_to_op_profit_pct:.2f}% in {latest_annual_period}."
                          if (cfo_conversion_delta_pp is not None and cfo_conversion_delta_pp < 0 and prior_cfo_to_op_profit_pct is not None)
                          else f"Operating cash flow conversion stands at {cfo_to_op_profit_pct:.2f}% of EBITDA in {latest_annual_period}."
                      )
                  )
                  + (
                      f" Conversion is below 100% of accounting EBITDA ({cfo_to_op_profit_pct:.2f}%)."
                      if cfo_to_op_profit_pct < 100.0
                      else (
                          f" Conversion exceeds 100% of accounting EBITDA ({cfo_to_op_profit_pct:.2f}%)."
                          if cfo_to_op_profit_pct > 100.0
                          else " Conversion is exactly 100% of accounting EBITDA."
                      )
                  )
              )
              if (cfo_to_op_profit_pct is not None and latest_annual_period)
              else "Cash flow conversion not available."
          ),
      },
      {
          "name": "Trade Receivables / Debtor Days (DSO)",
          "value": (
              f"{debtor_days_latest:.1f} days ({debtor_days_change:+.1f}d YoY)"
              if (
                  debtor_days_latest is not None
                  and debtor_days_change is not None
              )
              else (
                  f"{debtor_days_latest:.1f} days"
                  if debtor_days_latest is not None
                  else "N/A"
              )
          ),
          "period": f"Audited Annual: {cf_period_label}",
          "formula": "(Trade_Receivables / Audited_Annual_Sales) * 365",
          "calculation_steps": (
              f"Prior ({prior_annual_period}): {debtor_days_prior:.1f}d ->"
              f" Current ({latest_annual_period}): {debtor_days_latest:.1f}d"
              + (
                  f" (YoY Delta: {debtor_days_change:+.1f} days)"
                  if debtor_days_change is not None
                  else ""
              )
              if (
                  debtor_days_latest is not None
                  and debtor_days_prior is not None
              )
              else "N/A"
          ),
          "directional_comparison": (
              (
                  f"Trade debtor days (DSO) lengthened by +{debtor_days_change:.1f} days from {debtor_days_prior:.1f}d to {debtor_days_latest:.1f}d."
                  if (debtor_days_change is not None and debtor_days_change > 0 and debtor_days_prior is not None and debtor_days_latest is not None)
                  else (
                      f"Trade debtor days (DSO) shortened by {abs(debtor_days_change):.1f} days from {debtor_days_prior:.1f}d down to {debtor_days_latest:.1f}d."
                      if (debtor_days_change is not None and debtor_days_change < 0 and debtor_days_prior is not None and debtor_days_latest is not None)
                      else (
                          f"Trade debtor days (DSO) remained flat at {debtor_days_latest:.1f}d."
                          if (debtor_days_change == 0 and debtor_days_latest is not None)
                          else (
                              f"Trade debtor days (DSO) stand at {debtor_days_latest:.1f}d."
                              if debtor_days_latest is not None
                              else "Debtor days not available."
                          )
                      )
                  )
              )
          ),
      },
      {
          "name": "Days Inventory Outstanding (DIO)",
          "value": (
              f"{inv_days_latest:.1f} days ({inv_days_change:+.1f}d YoY)"
              if (inv_days_latest is not None and inv_days_change is not None)
              else (
                  f"{inv_days_latest:.1f} days"
                  if inv_days_latest is not None
                  else "N/A"
              )
          ),
          "period": f"Audited Annual: {cf_period_label}",
          "formula": "(Inventories / Cost_or_Sales_Base) * 365",
          "calculation_steps": (
              f"Prior ({prior_annual_period}): {inv_days_prior:.1f}d ->"
              f" Current ({latest_annual_period}): {inv_days_latest:.1f}d"
              + (
                  f" (YoY Delta: {inv_days_change:+.1f} days)"
                  if inv_days_change is not None
                  else ""
              )
              if (inv_days_latest is not None and inv_days_prior is not None)
              else "N/A"
          ),
          "directional_comparison": (
              (
                  f"Inventory days (DIO) lengthened by +{inv_days_change:.1f} days from {inv_days_prior:.1f}d to {inv_days_latest:.1f}d."
                  if (inv_days_change is not None and inv_days_change > 0 and inv_days_prior is not None and inv_days_latest is not None)
                  else (
                      f"Inventory days (DIO) shortened by {abs(inv_days_change):.1f} days from {inv_days_prior:.1f}d down to {inv_days_latest:.1f}d."
                      if (inv_days_change is not None and inv_days_change < 0 and inv_days_prior is not None and inv_days_latest is not None)
                      else (
                          f"Inventory days (DIO) remained flat at {inv_days_latest:.1f}d."
                          if (inv_days_change == 0 and inv_days_latest is not None)
                          else (
                              f"Inventory days (DIO) stand at {inv_days_latest:.1f}d."
                              if inv_days_latest is not None
                              else "Inventory days not available."
                          )
                      )
                  )
              )
          ),
      },
      {
          "name": "Cash Conversion Cycle (CCC) & Days Payable (DPO)",
          "value": (
              f"CCC: {ccc_latest:.1f}d ({ccc_change:+.1f}d) | DPO:"
              f" {payable_days_latest:.1f}d ({payable_days_change:+.1f}d)"
              if (
                  ccc_latest is not None
                  and payable_days_latest is not None
                  and ccc_change is not None
                  and payable_days_change is not None
              )
              else (
                  f"{ccc_latest:.1f} days" if ccc_latest is not None else "N/A"
              )
          ),
          "period": f"Audited Annual: {cf_period_label}",
          "formula": "CCC = Debtor_Days + Inventory_Days - Days_Payable",
          "calculation_steps": (
              f"{debtor_days_latest:.1f}d (DSO) + {inv_days_latest:.1f}d (DIO)"
              f" - {payable_days_latest:.1f}d (DPO) = {ccc_latest:.1f} days"
              f" (Prior CCC: {ccc_prior:.1f}d, Prior DPO:"
              f" {payable_days_prior:.1f}d)"
              if (
                  debtor_days_latest is not None
                  and inv_days_latest is not None
                  and payable_days_latest is not None
                  and ccc_latest is not None
                  and ccc_prior is not None
                  and payable_days_prior is not None
              )
              else "N/A"
          ),
          "directional_comparison": (
              (
                  (
                      f"Days payable (DPO) lengthened by +{payable_days_change:.1f} days from {payable_days_prior:.1f}d to {payable_days_latest:.1f}d"
                      if (payable_days_change is not None and payable_days_change > 0 and payable_days_prior is not None and payable_days_latest is not None)
                      else (
                          f"Days payable (DPO) contracted by {abs(payable_days_change):.1f} days from {payable_days_prior:.1f}d down to {payable_days_latest:.1f}d"
                          if (payable_days_change is not None and payable_days_change < 0 and payable_days_prior is not None and payable_days_latest is not None)
                          else (f"Days payable (DPO) stood flat at {payable_days_latest:.1f}d" if payable_days_latest is not None else "")
                      )
                  )
                  + (
                      (
                          f"; Cash Conversion Cycle (CCC) lengthened by +{ccc_change:.1f} days from {ccc_prior:.1f}d to {ccc_latest:.1f}d."
                          if (ccc_change is not None and ccc_change > 0 and ccc_prior is not None and ccc_latest is not None)
                          else (
                              f"; Cash Conversion Cycle (CCC) shortened by {abs(ccc_change):.1f} days from {ccc_prior:.1f}d down to {ccc_latest:.1f}d."
                              if (ccc_change is not None and ccc_change < 0 and ccc_prior is not None and ccc_latest is not None)
                              else (f"; Cash Conversion Cycle (CCC) stood flat at {ccc_latest:.1f}d." if ccc_latest is not None else ".")
                          )
                      )
                      if ccc_latest is not None
                      else "."
                  )
              ).strip("; ")
          ),
      },
  ]

  candidate_anomalies = []

  cfo_multi_quarter_trajectory = ""
  cfo_traj_parts = []
  for p_name in common_annual_periods[-4:]:
    c_val = cfo_by_period.get(p_name)
    op_val = pl_op_by_period.get(p_name)
    if c_val is not None and op_val and op_val > 0:
      conv = (c_val / op_val) * 100.0
      cfo_traj_parts.append(f"{p_name}: CFO ₹{c_val:,.1f} Cr / EBITDA ₹{op_val:,.1f} Cr ({conv:.1f}%)")
    elif c_val is not None:
      cfo_traj_parts.append(f"{p_name}: CFO ₹{c_val:,.1f} Cr")
  if cfo_traj_parts:
    cfo_multi_quarter_trajectory = " -> ".join(cfo_traj_parts)
  else:
    cfo_multi_quarter_trajectory = f"{prior_annual_period or 'Prior'} -> {latest_annual_period or 'Latest'}"

  if cfo_to_op_profit_pct is not None:
    cfo_delta = cfo_conversion_delta_pp or 0.0
    if (cfo_to_op_profit_pct is not None and cfo_to_op_profit_pct < 80.0) or cfo_delta < 0:
      sev = round(min(9.2, max(6.0, 6.0 + abs(cfo_delta) * 0.15 + (1.5 if (cfo_to_op_profit_pct and cfo_to_op_profit_pct < 80.0) else 0.0))), 1)
    else:
      sev = round(max(2.5, min(4.5, 4.2 - (0.5 if (cfo_to_op_profit_pct and cfo_to_op_profit_pct >= 90.0) else 0.0))), 1)

    if prior_cfo_to_op_profit_pct is not None:
      if cfo_delta > 0:
        cfo_dir_comp = (
            f"Operating cash flow conversion expanded by +{cfo_delta:.2f} pp "
            f"(from {prior_cfo_to_op_profit_pct:.2f}% in {prior_annual_period} "
            f"to {cfo_to_op_profit_pct:.2f}% in {latest_annual_period})."
        )
      elif cfo_delta < 0:
        cfo_dir_comp = (
            f"Operating cash flow conversion contracted by {abs(cfo_delta):.2f} pp "
            f"(from {prior_cfo_to_op_profit_pct:.2f}% in {prior_annual_period} "
            f"down to {cfo_to_op_profit_pct:.2f}% in {latest_annual_period})."
        )
      else:
        cfo_dir_comp = (
            f"Operating cash flow conversion remained flat at {cfo_to_op_profit_pct:.2f}% "
            f"in both {prior_annual_period} and {latest_annual_period}."
        )
      if cfo_to_op_profit_pct < 100.0:
        cfo_dir_comp += (
            f" Conversion is below 100% of accounting EBITDA ({cfo_to_op_profit_pct:.2f}%)."
        )
      elif cfo_to_op_profit_pct > 100.0:
        cfo_dir_comp += (
            f" Conversion exceeds 100% of accounting EBITDA ({cfo_to_op_profit_pct:.2f}%)."
        )
      else:
        cfo_dir_comp += " Conversion is exactly 100% of accounting EBITDA."
    else:
      cfo_dir_comp = (
          f"Operating cash flow conversion stands at {cfo_to_op_profit_pct:.2f}% of EBITDA in {latest_annual_period}."
      )
      if cfo_to_op_profit_pct < 100.0:
        cfo_dir_comp += f" Conversion is below 100% of accounting EBITDA ({cfo_to_op_profit_pct:.2f}%)."
      elif cfo_to_op_profit_pct > 100.0:
        cfo_dir_comp += f" Conversion exceeds 100% of accounting EBITDA ({cfo_to_op_profit_pct:.2f}%)."
      else:
        cfo_dir_comp += " Conversion is exactly 100% of accounting EBITDA."

    cfo_bullets = []
    if prior_annual_cfo is not None and latest_annual_cfo is not None:
      cfo_bullets.append(f"Operating Cash Flow (CFO): ₹{prior_annual_cfo:,.1f} Cr ({prior_annual_period}) -> ₹{latest_annual_cfo:,.1f} Cr ({latest_annual_period})")
    elif latest_annual_cfo is not None:
      cfo_bullets.append(f"Operating Cash Flow (CFO): ₹{latest_annual_cfo:,.1f} Cr ({latest_annual_period})")

    if prior_annual_op is not None and latest_annual_op is not None:
      cfo_bullets.append(f"Operating Profit (EBITDA): ₹{prior_annual_op:,.1f} Cr ({prior_annual_period}) -> ₹{latest_annual_op:,.1f} Cr ({latest_annual_period})")
    elif latest_annual_op is not None:
      cfo_bullets.append(f"Operating Profit (EBITDA): ₹{latest_annual_op:,.1f} Cr ({latest_annual_period})")

    if prior_cfo_to_op_profit_pct is not None and cfo_to_op_profit_pct is not None:
      cfo_bullets.append(f"CFO to EBITDA Conversion Rate: {prior_cfo_to_op_profit_pct:.2f}% ({prior_annual_period}) -> {cfo_to_op_profit_pct:.2f}% ({latest_annual_period}) ({cfo_delta:+.2f} pp YoY)")
    elif cfo_to_op_profit_pct is not None:
      cfo_bullets.append(f"CFO to EBITDA Conversion Rate: {cfo_to_op_profit_pct:.2f}% ({latest_annual_period})")

    if cfo_multi_quarter_trajectory:
      cfo_bullets.append(f"Historical Conversion Trajectory: {cfo_multi_quarter_trajectory}")

    candidate_anomalies.append({
        "id": "signal_cfo_ebitda",
        "metric": "Operating Cash Flow to EBITDA Conversion",
        "severity": sev,
        "directional_comparison": cfo_dir_comp,
        "multi_quarter_trajectory": cfo_multi_quarter_trajectory,
        "numbers_bullets": cfo_bullets,
        "summary": (
            f"Audited CFO/EBITDA conversion: {prior_cfo_to_op_profit_pct:.2f}%"
            f" ({prior_annual_period}) -> {cfo_to_op_profit_pct:.2f}%"
            f" ({latest_annual_period}) | YoY Shift: {cfo_delta:+.2f} pp. {cfo_dir_comp}"
            if prior_cfo_to_op_profit_pct is not None
            else (
                f"Audited CFO/EBITDA conversion: {cfo_to_op_profit_pct:.2f}%"
                f" ({latest_annual_period}). {cfo_dir_comp}"
            )
        ),
        "math_detail": (
            f"FY {latest_annual_period}: CFO ₹{latest_annual_cfo:,.1f} Cr /"
            f" Operating Profit ₹{latest_annual_op:,.1f} Cr ="
            f" {cfo_to_op_profit_pct:.2f}% (Prior {prior_annual_period}: CFO"
            f" ₹{prior_annual_cfo:,.1f} Cr / Operating Profit"
            f" ₹{prior_annual_op:,.1f} Cr = {prior_cfo_to_op_profit_pct:.2f}%)."
            if (
                prior_cfo_to_op_profit_pct is not None
                and prior_annual_cfo is not None
                and prior_annual_op is not None
            )
            else (
                f"CFO ₹{latest_annual_cfo:,.1f} Cr / Operating Profit"
                f" ₹{latest_annual_op:,.1f} Cr = {cfo_to_op_profit_pct:.2f}%."
            )
        ),
    })

  if expense_growth_yoy is not None and revenue_growth_yoy is not None:
    cost_wedge = round(expense_growth_yoy - revenue_growth_yoy, 2)
    if cost_wedge > 0 or (margin_change_pp is not None and margin_change_pp < 0):
      sev = round(min(9.2, max(6.5, 6.0 + max(0.0, cost_wedge) * 0.35 + (abs(margin_change_pp) * 0.35 if (margin_change_pp and margin_change_pp < 0) else 0.0))), 1)
    else:
      sev = round(max(2.5, min(4.5, 4.2 - abs(cost_wedge) * 0.1)), 1)

    if cost_wedge > 0:
      if expense_growth_yoy >= 0 and revenue_growth_yoy >= 0:
        wedge_comp = (
            f"Operating expenses ({expense_growth_yoy:+.2f}%) grew faster than net sales ({revenue_growth_yoy:+.2f}%), "
            f"creating an expense-to-sales wedge of +{cost_wedge:.2f} pp (operating costs outpaced revenue expansion)."
        )
      elif expense_growth_yoy >= 0 and revenue_growth_yoy < 0:
        wedge_comp = (
            f"Operating expenses expanded ({expense_growth_yoy:+.2f}%) while net sales contracted ({revenue_growth_yoy:+.2f}%), "
            f"creating an expense-to-sales wedge of +{cost_wedge:.2f} pp."
        )
      else:
        wedge_comp = (
            f"Operating expenses ({expense_growth_yoy:+.2f}%) outpaced net sales ({revenue_growth_yoy:+.2f}%), "
            f"creating an expense-to-sales wedge of +{cost_wedge:.2f} pp."
        )
    elif cost_wedge < 0:
      abs_wedge = abs(cost_wedge)
      if revenue_growth_yoy >= 0 and expense_growth_yoy >= 0:
        wedge_comp = (
            f"Net sales ({revenue_growth_yoy:+.2f}%) grew faster than operating expenses ({expense_growth_yoy:+.2f}%), "
            f"generating positive operating leverage of +{abs_wedge:.2f} pp (revenue expansion outpaced operating costs)."
        )
      elif revenue_growth_yoy >= 0 and expense_growth_yoy < 0:
        wedge_comp = (
            f"Net sales expanded ({revenue_growth_yoy:+.2f}%) while operating expenses contracted ({expense_growth_yoy:+.2f}%), "
            f"generating positive operating leverage of +{abs_wedge:.2f} pp."
        )
      else:
        wedge_comp = (
            f"Net sales ({revenue_growth_yoy:+.2f}%) outpaced operating expenses ({expense_growth_yoy:+.2f}%), "
            f"generating positive operating leverage of +{abs_wedge:.2f} pp."
        )
    else:
      wedge_comp = (
          f"Net sales and operating expenses changed at parity ({revenue_growth_yoy:+.2f}% YoY)."
      )

    if margin_change_pp is not None and prior_margin is not None and current_margin is not None:
      if margin_change_pp > 0:
        opm_comp = f" Operating margin expanded by +{margin_change_pp:.2f} pp (+{int(margin_change_pp * 100)} bps) from {prior_margin:.2f}% to {current_margin:.2f}%."
      elif margin_change_pp < 0:
        opm_comp = f" Operating margin contracted by {abs(margin_change_pp):.2f} pp ({int(margin_change_pp * 100)} bps) from {prior_margin:.2f}% down to {current_margin:.2f}%."
      else:
        opm_comp = f" Operating margin was flat at {current_margin:.2f}%."
    elif current_margin is not None:
      opm_comp = f" Operating margin stands at {current_margin:.2f}%."
    else:
      opm_comp = ""

    cost_dir_comp = f"{wedge_comp}{opm_comp}".strip()

    opm_summary_parts = []
    if current_margin is not None:
      opm_summary_parts.append(f", Operating Margin {current_margin:.2f}%")
      if margin_change_pp is not None:
        opm_summary_parts.append(f" ({margin_change_pp:+.2f} pp YoY)")
    opm_summary_str = "".join(opm_summary_parts)

    sales_math = (
        f"Sales: ₹{prior_sales:,.1f} Cr -> ₹{current_sales:,.1f} Cr ({revenue_growth_yoy:+.2f}%); "
        if (prior_sales is not None and current_sales is not None)
        else f"Net Sales YoY {revenue_growth_yoy:+.2f}%; "
    )
    exp_math = (
        f"Expenses: ₹{prior_expenses:,.1f} Cr -> ₹{current_expenses:,.1f} Cr ({expense_growth_yoy:+.2f}%);"
        if (prior_expenses is not None and current_expenses is not None)
        else f"Expenses YoY {expense_growth_yoy:+.2f}%;"
    )
    opm_math = ""
    if prior_margin is not None and current_margin is not None:
      opm_math = f" OPM: {prior_margin:.2f}% -> {current_margin:.2f}%."
    elif current_margin is not None:
      opm_math = f" OPM: {current_margin:.2f}%."

    q_traj_parts = []
    for q in quarterly_history:
      p_name = q.get("period", "")
      r_val = q.get("revenue")
      m_val = q.get("operating_margin_pct")
      if r_val is not None and m_val is not None:
        q_traj_parts.append(f"{p_name}: Sales ₹{r_val:,.1f} Cr | OPM {m_val:.2f}%")
      elif r_val is not None:
        q_traj_parts.append(f"{p_name}: Sales ₹{r_val:,.1f} Cr")
    margin_multi_quarter_trajectory = " -> ".join(q_traj_parts) if q_traj_parts else f"{prior_yoy_period or 'Prior'} -> {latest_period or 'Latest'}"

    margin_bullets = []
    if prior_sales is not None and current_sales is not None:
      margin_bullets.append(f"Net Sales (Quarter Ended {latest_period} vs YoY Baseline {prior_yoy_period}): ₹{prior_sales:,.1f} Cr ({prior_yoy_period}) -> ₹{current_sales:,.1f} Cr ({latest_period}) ({revenue_growth_yoy:+.2f}% YoY)")
    elif current_sales is not None:
      margin_bullets.append(f"Net Sales (Quarter Ended {latest_period}): ₹{current_sales:,.1f} Cr ({revenue_growth_yoy:+.2f}% YoY)")

    if prior_expenses is not None and current_expenses is not None:
      margin_bullets.append(f"Operating Expenses (Quarter Ended {latest_period} vs YoY Baseline {prior_yoy_period}): ₹{prior_expenses:,.1f} Cr ({prior_yoy_period}) -> ₹{current_expenses:,.1f} Cr ({latest_period}) ({expense_growth_yoy:+.2f}% YoY)")
    elif current_expenses is not None:
      margin_bullets.append(f"Operating Expenses (Quarter Ended {latest_period}): ₹{current_expenses:,.1f} Cr ({expense_growth_yoy:+.2f}% YoY)")

    margin_bullets.append(f"Expense-to-Sales Wedge: {cost_wedge:+.2f} pp ({expense_growth_yoy:+.2f}% expenses vs {revenue_growth_yoy:+.2f}% sales)")

    if prior_margin is not None and current_margin is not None:
      margin_bullets.append(f"Operating Profit Margin: {prior_margin:.2f}% -> {current_margin:.2f}% ({margin_change_pp:+.2f} pp / {int(margin_change_pp * 100):+d} bps)")
    elif current_margin is not None:
      margin_bullets.append(f"Operating Profit Margin: {current_margin:.2f}%")

    if prior_op is not None and current_op is not None:
      margin_bullets.append(f"Operating Profit (EBITDA ex-Other Income): ₹{prior_op:,.1f} Cr -> ₹{current_op:,.1f} Cr")
    elif current_op is not None:
      margin_bullets.append(f"Operating Profit (EBITDA ex-Other Income): ₹{current_op:,.1f} Cr")

    if margin_multi_quarter_trajectory:
      margin_bullets.append(f"Quarterly Trajectory: {margin_multi_quarter_trajectory}")

    candidate_anomalies.append({
        "id": "signal_margin_cost_dynamics",
        "metric": "Revenue vs Operating Expense & Margin Trajectory",
        "severity": sev,
        "directional_comparison": cost_dir_comp,
        "multi_quarter_trajectory": margin_multi_quarter_trajectory,
        "numbers_bullets": margin_bullets,
        "summary": (
            f"Quarterly ({latest_period} vs {prior_yoy_period}): Net Sales YoY"
            f" {revenue_growth_yoy:+.2f}%, Operating Expenses YoY"
            f" {expense_growth_yoy:+.2f}% (Expense-to-Sales Wedge:"
            f" {cost_wedge:+.2f} pp){opm_summary_str}. {cost_dir_comp}"
        ),
        "math_detail": f"{sales_math}{exp_math}{opm_math}".strip(),
    })

  ratios_periods = ratios_table.get("periods", [])
  clean_inv_series = _get_row_series(ratios_rows, ["Inventory Days", "InventoryDays", "DIO"])
  inv_traj_parts = []
  for p_idx, p_name in enumerate(ratios_periods):
    if p_idx < len(clean_inv_series):
      val = coerce_float(clean_inv_series[p_idx])
      if val is not None:
        inv_traj_parts.append(f"{p_name}: {val:.1f}d")
  dio_multi_quarter_trajectory = " -> ".join(inv_traj_parts[-5:]) if inv_traj_parts else f"{prior_annual_period}: {inv_days_prior:.1f}d -> {latest_annual_period}: {inv_days_latest:.1f}d"

  if inv_days_latest is not None and inv_days_prior is not None:
    inv_delta = inv_days_change or 0.0
    if inv_delta > 0 or (inv_days_latest is not None and inv_days_latest > 75.0):
      base_sev = 6.0 + max(0.0, inv_delta) * 0.2 + (max(0.0, (inv_days_latest - 75.0)) * 0.05 if inv_days_latest else 0.0)
      sev = round(min(9.0, max(6.0, base_sev)), 1)
    else:
      sev = round(max(2.5, min(4.5, 4.2 - abs(inv_delta) * 0.1)), 1)

    if inv_delta > 0:
      inv_dir_comp = (
          f"Inventory holding period (DIO) lengthened by +{inv_delta:.1f} days "
          f"from {inv_days_prior:.1f} days in {prior_annual_period} to {inv_days_latest:.1f} days in {latest_annual_period}, "
          f"indicating slower inventory turnover or buffer accumulation."
      )
    elif inv_delta < 0:
      inv_dir_comp = (
          f"Inventory holding period (DIO) shortened by {abs(inv_delta):.1f} days "
          f"from {inv_days_prior:.1f} days in {prior_annual_period} down to {inv_days_latest:.1f} days in {latest_annual_period}, "
          f"indicating faster inventory turnover or lean inventory."
      )
    else:
      inv_dir_comp = (
          f"Inventory holding period (DIO) remained flat at {inv_days_latest:.1f} days "
          f"in both {prior_annual_period} and {latest_annual_period}."
      )

    dio_bullets = [
        f"Days Inventory Outstanding (DIO): {inv_days_prior:.1f} days ({prior_annual_period}) -> {inv_days_latest:.1f} days ({latest_annual_period}) ({inv_delta:+.1f} days YoY)",
        f"Multi-Year DIO Trajectory: {dio_multi_quarter_trajectory}",
    ]

    candidate_anomalies.append({
        "id": "signal_inventory_dio",
        "metric": "Inventory Holding Velocity (DIO)",
        "severity": sev,
        "directional_comparison": inv_dir_comp,
        "multi_quarter_trajectory": dio_multi_quarter_trajectory,
        "numbers_bullets": dio_bullets,
        "summary": (
            f"Inventory Days (DIO): {inv_days_prior:.1f} days"
            f" ({prior_annual_period}) -> {inv_days_latest:.1f} days"
            f" ({latest_annual_period}) | YoY Shift: {inv_delta:+.1f} days. {inv_dir_comp}"
        ),
        "math_detail": (
            f"Historical DIO trajectory: {clean_inv_days[-4:]} across latest"
            f" audited fiscal years (YoY delta: {inv_delta:+.1f} days)."
        ),
    })

  clean_dpo_series = _get_row_series(ratios_rows, ["Days Payable", "DaysPayable", "DPO"])
  clean_ccc_series = _get_row_series(ratios_rows, ["Cash Conversion Cycle", "CashConversionCycle", "CCC"])
  ccc_traj_parts = []
  for p_idx, p_name in enumerate(ratios_periods):
    parts = []
    if p_idx < len(clean_dpo_series):
      dpo_val = coerce_float(clean_dpo_series[p_idx])
      if dpo_val is not None:
        parts.append(f"DPO {dpo_val:.1f}d")
    if p_idx < len(clean_ccc_series):
      ccc_val = coerce_float(clean_ccc_series[p_idx])
      if ccc_val is not None:
        parts.append(f"CCC {ccc_val:.1f}d")
    if parts:
      ccc_traj_parts.append(f"{p_name}: {', '.join(parts)}")
  pay_multi_quarter_trajectory = " -> ".join(ccc_traj_parts[-5:]) if ccc_traj_parts else f"{prior_annual_period} -> {latest_annual_period}"

  if (
      payable_days_latest is not None
      and payable_days_prior is not None
  ):
    pay_delta = payable_days_change or 0.0
    if pay_delta < 0 or (ccc_change is not None and ccc_change > 0):
      sev = round(min(8.8, max(5.8, 5.5 + abs(pay_delta) * 0.15 + (max(0.0, ccc_change) * 0.15 if ccc_change else 0.0))), 1)
    else:
      sev = round(max(2.5, min(4.5, 4.0)), 1)

    if pay_delta > 0:
      pay_comp = (
          f"Supplier payable days (DPO) lengthened by +{pay_delta:.1f} days "
          f"from {payable_days_prior:.1f} to {payable_days_latest:.1f} days "
          f"(company took longer to pay vendors)."
      )
    elif pay_delta < 0:
      pay_comp = (
          f"Supplier payable days (DPO) contracted by {abs(pay_delta):.1f} days "
          f"from {payable_days_prior:.1f} down to {payable_days_latest:.1f} days "
          f"(company paid vendors faster)."
      )
    else:
      pay_comp = f"Supplier payable days (DPO) remained flat at {payable_days_latest:.1f} days."

    if ccc_change is not None and ccc_prior is not None and ccc_latest is not None:
      if ccc_change > 0:
        ccc_comp = f" Net cash conversion cycle (CCC) lengthened by +{ccc_change:.1f} days from {ccc_prior:.1f} to {ccc_latest:.1f} days."
      elif ccc_change < 0:
        ccc_comp = f" Net cash conversion cycle (CCC) shortened by {abs(ccc_change):.1f} days from {ccc_prior:.1f} down to {ccc_latest:.1f} days."
      else:
        ccc_comp = f" Net cash conversion cycle (CCC) was flat at {ccc_latest:.1f} days."
    elif ccc_latest is not None:
      ccc_comp = f" Net cash conversion cycle (CCC) stands at {ccc_latest:.1f} days."
    else:
      ccc_comp = ""

    pay_dir_comp = f"{pay_comp}{ccc_comp}".strip()

    ccc_summary_part = ""
    if ccc_latest is not None and ccc_prior is not None:
      ccc_chg_str = f" ({ccc_change:+.1f}d)" if ccc_change is not None else ""
      ccc_summary_part = f" | Cash Conversion Cycle (CCC): {ccc_prior:.1f}d -> {ccc_latest:.1f}d{ccc_chg_str}"
    elif ccc_latest is not None:
      ccc_summary_part = f" | Cash Conversion Cycle (CCC): {ccc_latest:.1f}d"

    ccc_calc_parts = []
    if debtor_days_latest is not None:
      ccc_calc_parts.append(f"{debtor_days_latest:.1f}d (DSO)")
    if inv_days_latest is not None:
      ccc_calc_parts.append(f"+ {inv_days_latest:.1f}d (DIO)")
    ccc_calc_parts.append(f"- {payable_days_latest:.1f}d (DPO)")
    if ccc_latest is not None:
      ccc_calc_parts.append(f"= {ccc_latest:.1f}d")
    ccc_formula_str = " ".join(ccc_calc_parts)

    ccc_plain_str = (
        f", with net Cash Conversion Cycle at {ccc_latest:.1f} days"
        if ccc_latest is not None
        else ""
    )

    pay_bullets = [
        f"Days Payable Outstanding (DPO): {payable_days_prior:.1f} days ({prior_annual_period}) -> {payable_days_latest:.1f} days ({latest_annual_period}) ({pay_delta:+.1f} days YoY)",
    ]
    if ccc_latest is not None and ccc_prior is not None:
      pay_bullets.append(f"Cash Conversion Cycle (CCC): {ccc_prior:.1f} days ({prior_annual_period}) -> {ccc_latest:.1f} days ({latest_annual_period}) ({ccc_change:+.1f} days YoY)")
    if debtor_days_latest is not None and inv_days_latest is not None and payable_days_latest is not None and ccc_latest is not None:
      pay_bullets.append(f"Working Capital Formula: {debtor_days_latest:.1f}d DSO + {inv_days_latest:.1f}d DIO - {payable_days_latest:.1f}d DPO = {ccc_latest:.1f}d CCC")
    pay_bullets.append(f"Multi-Year Working Capital Trajectory: {pay_multi_quarter_trajectory}")

    candidate_anomalies.append({
        "id": "signal_payables_ccc",
        "metric": "Supplier Payable Terms (DPO) & Cash Conversion Cycle (CCC)",
        "severity": sev,
        "directional_comparison": pay_dir_comp,
        "multi_quarter_trajectory": pay_multi_quarter_trajectory,
        "numbers_bullets": pay_bullets,
        "summary": (
            f"Days Payable (DPO): {payable_days_prior:.1f} days"
            f" ({prior_annual_period}) -> {payable_days_latest:.1f} days"
            f" ({latest_annual_period}) | YoY Shift: {pay_delta:+.1f} days"
            f"{ccc_summary_part}. {pay_dir_comp}"
        ),
        "math_detail": (
            f"DPO history: {clean_payable_days[-4:]}; CCC history:"
            f" {clean_ccc[-4:]} ({ccc_formula_str})."
        ),
    })

  clean_dso_series = _get_row_series(ratios_rows, ["Debtor Days", "DebtorDays", "DSO"])
  dso_traj_parts = []
  for p_idx, p_name in enumerate(ratios_periods):
    if p_idx < len(clean_dso_series):
      val = coerce_float(clean_dso_series[p_idx])
      if val is not None:
        dso_traj_parts.append(f"{p_name}: {val:.1f}d")
  dso_multi_quarter_trajectory = " -> ".join(dso_traj_parts[-5:]) if dso_traj_parts else f"{prior_annual_period}: {debtor_days_prior:.1f}d -> {latest_annual_period}: {debtor_days_latest:.1f}d"

  if debtor_days_latest is not None and debtor_days_prior is not None:
    deb_delta = debtor_days_change or 0.0
    if deb_delta > 0 or (debtor_days_latest is not None and debtor_days_latest > 25.0):
      base_sev = 6.0 + max(0.0, deb_delta) * 0.3 + (max(0.0, (debtor_days_latest - 25.0)) * 0.08 if debtor_days_latest else 0.0)
      sev = round(min(9.0, max(6.0, base_sev)), 1)
    else:
      sev = round(max(2.5, min(4.5, 4.2 - abs(deb_delta) * 0.1)), 1)

    if deb_delta > 0:
      deb_dir_comp = (
          f"Trade debtor days (DSO) lengthened by +{deb_delta:.1f} days "
          f"from {debtor_days_prior:.1f} days in {prior_annual_period} to {debtor_days_latest:.1f} days in {latest_annual_period}, "
          f"indicating slower customer collections or extended distributor credit."
      )
    elif deb_delta < 0:
      deb_dir_comp = (
          f"Trade debtor days (DSO) shortened by {abs(deb_delta):.1f} days "
          f"from {debtor_days_prior:.1f} days in {prior_annual_period} down to {debtor_days_latest:.1f} days in {latest_annual_period}, "
          f"indicating faster customer collections."
      )
    else:
      deb_dir_comp = (
          f"Trade debtor days (DSO) remained flat at {debtor_days_latest:.1f} days "
          f"in both {prior_annual_period} and {latest_annual_period}."
      )

    deb_bullets = [
        f"Trade Debtor Days (DSO): {debtor_days_prior:.1f} days ({prior_annual_period}) -> {debtor_days_latest:.1f} days ({latest_annual_period}) ({deb_delta:+.1f} days YoY)",
        f"Multi-Year DSO Trajectory: {dso_multi_quarter_trajectory}",
    ]

    candidate_anomalies.append({
        "id": "signal_debtor_days",
        "metric": "Distributor & Channel Credit Velocity (Debtor Days / DSO)",
        "severity": sev,
        "directional_comparison": deb_dir_comp,
        "multi_quarter_trajectory": dso_multi_quarter_trajectory,
        "numbers_bullets": deb_bullets,
        "summary": (
            f"Trade Debtor Days (DSO): {debtor_days_prior:.1f} days"
            f" ({prior_annual_period}) -> {debtor_days_latest:.1f} days"
            f" ({latest_annual_period}) | YoY Shift: {deb_delta:+.1f} days. {deb_dir_comp}"
        ),
        "math_detail": (
            f"DSO trajectory across recent audited years:"
            f" {clean_debtor_days[-4:]} (YoY change: {deb_delta:+.1f} days)."
        ),
    })

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
      "inventory_days_prior": inv_days_prior,
      "inventory_days_change": inv_days_change,
      "payable_days_latest": payable_days_latest,
      "payable_days_prior": payable_days_prior,
      "payable_days_change": payable_days_change,
      "ccc_latest": ccc_latest,
      "ccc_prior": ccc_prior,
      "ccc_change": ccc_change,
      "working_capital_days_latest": wc_days_latest,
      "working_capital_days_change": wc_days_change,
      "cfo_to_op_profit_pct": cfo_to_op_profit_pct,
      "prior_cfo_to_op_profit_pct": prior_cfo_to_op_profit_pct,
      "cfo_conversion_delta_pp": cfo_conversion_delta_pp,
      "latest_annual_cfo": latest_annual_cfo,
      "latest_annual_op": latest_annual_op,
      "key_numbers": key_numbers,
      "red_flags": top_5_anomalies,
      "anomalies": top_5_anomalies,
      "quarterly_history": quarterly_history,
  }