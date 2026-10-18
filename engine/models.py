from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AnomalyCandidate(BaseModel):
    """
    Represents a statistically significant accounting divergence flagged by the math sandbox.
    """
    metric_name: str
    metric_type: str = Field(description="Normalized type: uvg_divergence, debtor_days, margin_wedge, cfo_conversion")
    unit: str = Field(description="Unit of measurement: %, d, bps")
    period: str
    target_value: float
    baseline_value: float
    delta: float
    materiality: float
    severity_score: float = Field(description="Priority score = abs(delta) * materiality")
    description: str
    timeline_trajectory: str = Field(default="", description="Multi-quarter trajectory tracking baseline to current")

class ForensicSummary(BaseModel):
    ticker: str
    company_name: str
    quarters_analyzed: List[str]
    debtor_days: Dict[str, float]
    sales_growth_yoy: Dict[str, float]
    derived_volume_growth: Dict[str, float] = Field(default_factory=dict, description="Historical derived underlying volume growth (P x Q decomposition)")
    
    # Beneish M-Score Sub-Indices (Feature A)
    beneish_dsri: Optional[float] = Field(default=None, description="Days Sales in Receivables Index (Receivables/Sales YoY ratio)")
    beneish_sgi: Optional[float] = Field(default=None, description="Sales Growth Index (YoY sales ratio)")
    beneish_gmi: Optional[float] = Field(default=None, description="Gross Margin Index (Prior Margin / Current Margin)")
    beneish_aqi: Optional[float] = Field(default=None, description="Asset Quality Index (Non-current asset capitalization proxy)")
    
    # Cash Conversion & Quality
    cfo_to_ebitda: Optional[float] = Field(default=None, description="Operating Cash Flow to EBITDA cash conversion ratio")
    
    # Quick Commerce Dilution & Margin Wedge (Feature C)
    margin_wedge_bps: Optional[float] = Field(default=None, description="Gross Margin delta - EBITDA margin delta in basis points")
    distribution_drag_bps: Optional[float] = Field(default=None, description="Operating Expense / Sales expansion in basis points")
    
    # Multi-Peer Relative Spread (Feature E)
    peer_spread_days: Optional[float] = Field(default=None, description="Target debtor stretch minus peer median debtor stretch")
    peer_comparison: Dict[str, Any] = Field(default_factory=dict, description="Peer benchmarking data")
    
    anomalies: List[AnomalyCandidate]
