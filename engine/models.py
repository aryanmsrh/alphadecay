from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class AnomalyCandidate(BaseModel):
    """
    Represents a statistically significant accounting divergence flagged by the math sandbox.
    """
    metric_name: str
    period: str
    target_value: float
    baseline_value: float
    delta: float
    materiality: float
    severity_score: float = Field(description="Priority score = abs(delta) * materiality")
    description: str

class ForensicSummary(BaseModel):
    ticker: str
    company_name: str
    quarters_analyzed: List[str]
    debtor_days: Dict[str, float]
    sales_growth_yoy: Dict[str, float]
    cfo_to_ebitda: Optional[float] = None
    margin_wedge_bps: Optional[float] = None
    anomalies: List[AnomalyCandidate]
