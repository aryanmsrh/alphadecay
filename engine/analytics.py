"""
ALPHA-DECAY Deterministic Financial Analytics Layer.
Pure Python, typed, zero LLM arithmetic.
Implements canonical financial formulas (Beneish DSRI, SGI, GMI, AQI),
distinguishes heuristic residuals from reported volume growth,
handles zero/missing values explicitly without synthetic substitution,
and enforces mathematical invariants.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import date, datetime, timezone
from pydantic import BaseModel, Field
from engine.periods import ReportingPeriod, PeriodAligner, PeriodAlignmentResult


class FinancialObservation(BaseModel):
    """
    Normalized, typed internal representation for a single financial observation with complete provenance.
    Never silently overwrites raw source values with normalized values.
    """
    company_id: str
    ticker: str
    metric_name: str
    canonical_definition: str = Field(default="", description="Formal accounting identity or formula")
    raw_source_value: Any = Field(description="Exact value as ingested from raw table cell")
    numeric_value: Optional[float] = Field(default=None, description="Cleaned, parsed numeric value")
    currency: str = "INR"
    unit: str = "Cr"  # "Cr", "bps", "%", "d", "ratio"
    period: ReportingPeriod
    frequency: str = "quarterly"  # "quarterly", "annual"
    statement_type: str = "consolidated"  # "consolidated", "standalone"
    source_url: Optional[str] = None
    source_type: str = "screener"  # "regulatory_filing", "screener", "concall"
    publisher: str = "Exchange / Regulatory Authority"
    publication_date: Optional[date] = None
    retrieval_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    table_name: Optional[str] = None
    row_label: Optional[str] = None
    source_locator: Optional[str] = None  # e.g. "quarters_table[Sales][2025-03-31]"
    is_reported: bool = True
    is_calculated: bool = False
    is_estimated: bool = False
    is_imputed: bool = False
    validation_status: str = "VALID"  # "VALID", "MISSING", "UNPARSEABLE", "NOT_APPLICABLE"
    limitations: Optional[str] = None
    transformations_applied: Optional[str] = None


class BeneishComponents(BaseModel):
    """
    Audited breakdown of Beneish M-Score sub-indices.
    Explicitly distinguishes complete from partial calculations.
    """
    # Canonical sub-indices
    dsri: Optional[float] = Field(default=None, description="Days Sales in Receivables Index (Canonical: (AR_t/Sales_t)/(AR_prev/Sales_prev))")
    sgi: Optional[float] = Field(default=None, description="Sales Growth Index (Sales_t / Sales_prev)")
    gmi: Optional[float] = Field(default=None, description="Gross Margin Index (Canonical: GrossMargin_prev / GrossMargin_t)")
    aqi: Optional[float] = Field(default=None, description="Asset Quality Index (Canonical)")
    depi: Optional[float] = Field(default=None, description="Depreciation Index")
    sgai: Optional[float] = Field(default=None, description="Sales, General & Admin Expense Index")
    lvgi: Optional[float] = Field(default=None, description="Leverage Index")
    tata: Optional[float] = Field(default=None, description="Total Accruals to Total Assets")

    # Proxy sub-indices (explicitly separated from canonical components)
    debtor_days_ratio_proxy: Optional[float] = Field(default=None, description="Ratio of Debtor Days (Proxy, NOT canonical DSRI)")
    opm_margin_ratio_proxy: Optional[float] = Field(default=None, description="OPM ratio proxy (Prior OPM / Current OPM, NOT canonical GMI)")

    is_complete_m_score: bool = False
    composite_m_score: Optional[float] = None
    missing_components: List[str] = Field(default_factory=list)
    interpretation_note: str = ""


class MetricGrowthResult(BaseModel):
    """Result of growth computation between two aligned periods."""
    target_period: str
    baseline_period: str
    target_value: float
    baseline_value: float
    growth_pct: float
    comparison_type: str  # "yoy", "qoq"


class ExpenseResidualResult(BaseModel):
    """
    Expense-adjusted revenue growth residual.
    HEURISTIC screening metric, NOT company-reported unit volume growth.
    """
    period: str
    sales_growth_yoy: float
    expense_growth_yoy: float
    cost_to_sales_ratio: float
    expense_adjusted_revenue_growth_residual: float
    is_reported_volume: bool = False
    caveat: str = (
        "Heuristic screening residual. Assumes expense changes approximate realization. "
        "Does NOT constitute company-reported unit volume growth, pricing power, or causal proof."
    )


class FinancialAnalytics:
    """
    Deterministic financial formulas with strict input validation, clear documentation,
    and zero LLM arithmetic.
    """

    @staticmethod
    def calculate_growth(
        target_val: Optional[float],
        baseline_val: Optional[float]
    ) -> Optional[float]:
        """
        Canonical percentage growth: ((target - baseline) / baseline) * 100.
        
        Inputs: target_val, baseline_val (both numeric).
        Denominator constraint: baseline_val must be strictly > 0.
        Missingness behavior: returns None if baseline is zero, negative, or either input is None.
        Rounding: rounded to 2 decimal places.
        """
        if target_val is None or baseline_val is None:
            return None
        if baseline_val <= 0:
            return None
        return round(((target_val - baseline_val) / baseline_val) * 100.0, 2)

    @staticmethod
    def compute_canonical_dsri(
        ar_t: Optional[float],
        sales_t: Optional[float],
        ar_prev: Optional[float],
        sales_prev: Optional[float]
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Canonical Beneish Days' Sales in Receivables Index:
        DSRI = (AR_t / Sales_t) / (AR_{t-1} / Sales_{t-1})
        
        Inputs: Trade Receivables and Net Sales for current (t) and prior (t-1) periods.
        Required statement duration: must be from identical frequencies (annual vs annual, or matching quarters).
        Denominator constraints: sales_t > 0, sales_prev > 0, (ar_prev / sales_prev) > 0.
        Returns: (dsri, error_reason)
        """
        if None in (ar_t, sales_t, ar_prev, sales_prev):
            return None, "Missing receivables or sales inputs for one or both periods"
        if sales_t <= 0:
            return None, f"Current sales ({sales_t}) is zero or negative; invalid denominator"
        if sales_prev <= 0:
            return None, f"Prior sales ({sales_prev}) is zero or negative; invalid denominator"

        ratio_curr = ar_t / sales_t
        ratio_prev = ar_prev / sales_prev

        if ratio_prev <= 0:
            return None, f"Prior AR/Sales ratio ({ratio_prev}) is zero or negative; invalid denominator"

        dsri = round(ratio_curr / ratio_prev, 3)
        return dsri, None

    @staticmethod
    def compute_debtor_days_ratio_proxy(
        days_t: Optional[float],
        days_prev: Optional[float]
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Ratio of statutory debtor days: Debtor_Days_t / Debtor_Days_{t-1}.
        Labeled strictly as a proxy; mathematically distinct from canonical DSRI.
        """
        if days_t is None or days_prev is None:
            return None, "Missing debtor days for one or both periods"
        if days_prev <= 0:
            return None, f"Prior debtor days ({days_prev}) is <= 0"
        return round(days_t / days_prev, 3), None

    @staticmethod
    def compute_expense_adjusted_residual(
        sales_growth_yoy: Optional[float],
        expenses_t: Optional[float],
        expenses_prev: Optional[float],
        sales_t: Optional[float]
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Expense-adjusted revenue growth residual:
        residual = sales_growth_yoy - (expense_growth_yoy * (expenses_t / sales_t))
        
        Strict policy:
        This is a HEURISTIC screening residual. It does not isolate unit volume growth
        or pricing power, and must never be labeled as reported volume data.
        """
        if None in (sales_growth_yoy, expenses_t, expenses_prev, sales_t):
            return None, "Missing inputs for expense residual calculation"
        if expenses_prev <= 0 or sales_t <= 0:
            return None, "Invalid denominator for expenses or sales"

        exp_growth = ((expenses_t - expenses_prev) / expenses_prev) * 100.0
        cost_ratio = expenses_t / sales_t
        exp_effect = exp_growth * cost_ratio
        residual = round(sales_growth_yoy - exp_effect, 2)
        return residual, None

    @staticmethod
    def compute_beneish_sub_indices(
        sales_t: Optional[float],
        sales_prev: Optional[float],
        cogs_t: Optional[float] = None,
        cogs_prev: Optional[float] = None,
        gross_profit_t: Optional[float] = None,
        gross_profit_prev: Optional[float] = None,
        opm_t: Optional[float] = None,
        opm_prev: Optional[float] = None,
        other_assets_t: Optional[float] = None,
        total_assets_t: Optional[float] = None,
        other_assets_prev: Optional[float] = None,
        total_assets_prev: Optional[float] = None,
        current_assets_t: Optional[float] = None,
        current_assets_prev: Optional[float] = None,
        ppe_t: Optional[float] = None,
        ppe_prev: Optional[float] = None,
        ar_t: Optional[float] = None,
        ar_prev: Optional[float] = None,
        debtor_days_t: Optional[float] = None,
        debtor_days_prev: Optional[float] = None
    ) -> BeneishComponents:
        """
        Audited calculation of available Beneish sub-indices.
        Does NOT fabricate a complete M-score if required components are missing.
        """
        missing = []

        # 1. DSRI
        dsri, dsri_err = FinancialAnalytics.compute_canonical_dsri(ar_t, sales_t, ar_prev, sales_prev)
        if dsri is None:
            missing.append(f"Canonical DSRI ({dsri_err})")

        # Debtor Days Proxy
        dd_proxy, _ = FinancialAnalytics.compute_debtor_days_ratio_proxy(debtor_days_t, debtor_days_prev)

        # 2. SGI: Sales Growth Index
        sgi = None
        if sales_t is not None and sales_prev is not None and sales_prev > 0:
            sgi = round(sales_t / sales_prev, 3)
        else:
            missing.append("SGI (Sales unavailable or <= 0)")

        # 3. GMI: Gross Margin Index (prior gross margin / current gross margin)
        # Canonical GMI strictly requires Gross Margin or COGS
        gmi = None
        opm_proxy = None
        if gross_profit_t is not None and gross_profit_prev is not None and sales_t and sales_prev and sales_t > 0 and sales_prev > 0:
            gm_curr = gross_profit_t / sales_t
            gm_prev = gross_profit_prev / sales_prev
            if gm_curr > 0:
                gmi = round(gm_prev / gm_curr, 3)
            else:
                missing.append("GMI (Current gross margin <= 0)")
        elif cogs_t is not None and cogs_prev is not None and sales_t and sales_prev and sales_t > 0 and sales_prev > 0:
            gm_curr = (sales_t - cogs_t) / sales_t
            gm_prev = (sales_prev - cogs_prev) / sales_prev
            if gm_curr > 0:
                gmi = round(gm_prev / gm_curr, 3)
            else:
                missing.append("GMI (Current gross margin <= 0)")
        else:
            missing.append("Canonical GMI (COGS or Gross Profit disclosures unavailable)")

        # OPM Ratio Proxy (explicitly separated from canonical GMI)
        if opm_t is not None and opm_prev is not None and opm_t > 0:
            opm_proxy = round(opm_prev / opm_t, 3)

        # 4. AQI: Asset Quality Index
        # Canonical AQI = [1 - (Current Assets + PPE + Securities) / Total Assets]_t / [1 - (Current Assets + PPE + Securities) / Total Assets]_{t-1}
        # Non-current assets other than PPE / Total assets
        aqi = None
        if None not in (other_assets_t, total_assets_t, other_assets_prev, total_assets_prev):
            if total_assets_t > 0 and total_assets_prev > 0:
                aq_curr = other_assets_t / total_assets_t
                aq_prev = other_assets_prev / total_assets_prev
                if aq_prev > 0:
                    aqi = round(aq_curr / aq_prev, 3)
                else:
                    # Never default to 1.0! AQI is undefined if baseline is 0
                    aqi = None
                    missing.append("AQI (Prior non-current asset ratio is 0)")
        if aqi is None and "AQI (Prior non-current asset ratio is 0)" not in missing:
            missing.append("AQI (Asset breakdown missing or incomplete)")

        # 5-8. Components typically missing from quarterly statutory tables
        missing.extend([
            "DEPI (Depreciation Index: Prior Depr Rate / Current Depr Rate)",
            "SGAI (SGA Expense Index: SGA_t/Sales_t vs SGA_prev/Sales_prev)",
            "LVGI (Leverage Index: Total Debt / Total Assets)",
            "TATA (Total Accruals to Total Assets: (Net Income - CFO) / Total Assets)"
        ])

        note = (
            "Screening indicators only. Partial Beneish disclosures available; "
            "composite M-Score is not computed to avoid false precision. "
            "Exceeding sub-index benchmarks indicates screening anomalies, not conclusive evidence of manipulation."
        )

        return BeneishComponents(
            dsri=dsri,
            sgi=sgi,
            gmi=gmi,
            aqi=aqi,
            debtor_days_ratio_proxy=dd_proxy,
            opm_margin_ratio_proxy=opm_proxy,
            is_complete_m_score=False,
            composite_m_score=None,
            missing_components=missing,
            interpretation_note=note
        )

    @staticmethod
    def compute_channel_margin_metrics(
        sales_t: Optional[float],
        sales_prev: Optional[float],
        expenses_t: Optional[float],
        expenses_prev: Optional[float],
        opm_t: Optional[float],
        opm_prev: Optional[float],
        cogs_t: Optional[float] = None,
        cogs_prev: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Computes margin movements and expense-to-sales shifts in basis points.
        
        Only computes gross-versus-operating margin wedge if Gross Margin / COGS is available.
        Otherwise provides operating margin delta and expense-to-sales ratio change.
        """
        # 1. Expense-to-sales ratio change
        exp_to_sales_bps = None
        if None not in (sales_t, sales_prev, expenses_t, expenses_prev) and sales_t > 0 and sales_prev > 0:
            curr_cost_ratio = expenses_t / sales_t
            prev_cost_ratio = expenses_prev / sales_prev
            exp_to_sales_bps = round((curr_cost_ratio - prev_cost_ratio) * 10000.0, 1)

        # 2. Operating margin delta
        delta_opm_bps = None
        if opm_t is not None and opm_prev is not None:
            delta_opm = opm_t - opm_prev
            delta_opm_bps = round(delta_opm * 100.0, 1)

        # 3. Canonical Gross-vs-Operating Margin Wedge
        margin_wedge_bps = None
        wedge_is_canonical = False
        if None not in (sales_t, sales_prev, cogs_t, cogs_prev) and sales_t > 0 and sales_prev > 0 and delta_opm_bps is not None:
            gm_curr = (sales_t - cogs_t) / sales_t
            gm_prev = (sales_prev - cogs_prev) / sales_prev
            delta_gm_bps = (gm_curr - gm_prev) * 10000.0
            # Wedge = Gross Margin change - Operating Margin change
            margin_wedge_bps = round(delta_gm_bps - delta_opm_bps, 1)
            wedge_is_canonical = True
        elif delta_opm_bps is not None:
            # Canonical gross margin unavailable; do not substitute absolute delta as a canonical wedge!
            margin_wedge_bps = None
            wedge_is_canonical = False

        return {
            "expense_to_sales_ratio_change_bps": exp_to_sales_bps,
            "distribution_drag_bps": exp_to_sales_bps,  # Backward compatibility alias
            "operating_margin_delta_bps": delta_opm_bps,
            "margin_wedge_bps": margin_wedge_bps,
            "margin_wedge_is_canonical": wedge_is_canonical
        }
