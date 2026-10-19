from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
from engine.analytics import BeneishComponents, FinancialObservation


class AnomalyCandidate(BaseModel):
    """
    Represents an audited accounting divergence flagged by the deterministic math sandbox.
    Clearly specifies comparison basis, materiality, severity score, and whether metric is heuristic.
    """
    metric_name: str
    metric_type: str = Field(description="Normalized type: expense_residual_divergence, debtor_days, margin_wedge, cfo_conversion")
    unit: str = Field(description="Unit of measurement: %, d, bps, ratio")
    period: str
    target_value: float
    baseline_value: float
    delta: float
    materiality: float
    severity_score: float = Field(description="Priority score = abs(delta) * materiality * weighting")
    description: str
    timeline_trajectory: str = Field(default="", description="Multi-quarter trajectory tracking baseline to current")
    is_heuristic: bool = Field(default=False, description="True if metric is a heuristic screening indicator rather than reported fact")
    comparison_basis: str = Field(default="YoY", description="Explicit comparison basis: 'YoY' (Year-over-Year) or 'QoQ' (Sequential Quarter)")
    direction: str = Field(default="adverse", description="'adverse' (deterioration), 'favorable' (improvement), or 'neutral'")


class ForensicSummary(BaseModel):
    """
    Complete deterministic forensic audit result envelope for an entity.
    Maintains provenance of all calculations, separates canonical from proxy metrics,
    and supports a genuine NO_MATERIAL_ANOMALY_DETECTED state.
    """
    ticker: str
    company_name: str
    quarters_analyzed: List[str]
    debtor_days: Dict[str, Optional[float]] = Field(default_factory=dict)
    sales_growth_yoy: Dict[str, Optional[float]]
    
    # Corrected metric: expense-adjusted revenue growth residual (heuristic screening metric)
    expense_adjusted_residual: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="Expense-adjusted revenue growth residual (screening heuristic, NOT unit-volume growth)"
    )
    
    # Backward compatibility alias
    @property
    def derived_volume_growth(self) -> Dict[str, Optional[float]]:
        return self.expense_adjusted_residual

    # Beneish M-Score Sub-Indices (Canonical vs Proxy)
    beneish_dsri: Optional[float] = Field(default=None, description="Canonical Days Sales in Receivables Index (Receivables/Sales YoY ratio)")
    debtor_days_ratio_proxy: Optional[float] = Field(default=None, description="Debtor days ratio proxy (Debtor Days_t / Debtor Days_{t-1})")
    beneish_sgi: Optional[float] = Field(default=None, description="Sales Growth Index (YoY sales ratio)")
    beneish_gmi: Optional[float] = Field(default=None, description="Canonical Gross Margin Index (Prior GM / Current GM)")
    opm_margin_ratio_proxy: Optional[float] = Field(default=None, description="Operating Profit Margin proxy for GMI")
    beneish_aqi: Optional[float] = Field(default=None, description="Asset Quality Index")
    beneish_components: Optional[BeneishComponents] = Field(default=None, description="Audited Beneish breakdown with missing components")
    
    # Cash Conversion & Quality (operating cash flow divided by operating profit)
    cfo_to_operating_profit: Optional[float] = Field(default=None, description="Operating Cash Flow to Trailing Operating Profit ratio")
    
    # Backward compatibility alias
    @property
    def cfo_to_ebitda(self) -> Optional[float]:
        return self.cfo_to_operating_profit
    
    # Channel Margin Movements
    margin_wedge_bps: Optional[float] = Field(default=None, description="Gross Margin delta - Operating Margin delta in basis points")
    margin_wedge_is_canonical: bool = Field(default=False, description="True if both gross and operating margins were available")
    operating_margin_delta_bps: Optional[float] = Field(default=None, description="Operating Margin YoY change in basis points")
    expense_to_sales_ratio_change_bps: Optional[float] = Field(default=None, description="Total Expense / Sales expansion in basis points")
    
    # Backward compatibility alias
    @property
    def distribution_drag_bps(self) -> Optional[float]:
        return self.expense_to_sales_ratio_change_bps
    
    # Multi-Peer Relative Spread
    peer_spread_days: Optional[float] = Field(default=None, description="Target metric delta minus peer median delta")
    peer_comparison: Dict[str, Any] = Field(default_factory=dict, description="Peer benchmarking data and synchronicity status")
    
    # Metadata & Tracking
    sector: Optional[str] = Field(default="Consumer, FMCG & Retail", description="Industry classification track")
    as_of_date: Optional[str] = Field(default=None, description="Point-in-time cutoff date (YYYY-MM-DD)")
    model_used: Optional[str] = Field(default=None, description="Name of LLM model executed")
    thinking_level: Optional[str] = Field(default=None, description="Thinking effort configured")
    provider_used: Optional[str] = Field(default=None, description="Model provider actually executed")

    # Anomalies and Genuine No-Anomaly State
    anomalies: List[AnomalyCandidate] = Field(default_factory=list)
    no_material_anomaly_detected: bool = Field(default=False, description="True if no material accounting divergence exceeded screening thresholds")
    
    # Typed Observation Registry and Audit Notes
    observations: List[FinancialObservation] = Field(default_factory=list, description="Typed, auditable raw-to-normalized observations")
    data_limitations: List[str] = Field(default_factory=list, description="Disclosed data-quality or coverage gaps")

    model_config = ConfigDict(extra="allow")
