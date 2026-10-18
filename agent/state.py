from typing import TypedDict, List, Dict, Any, Optional

class InvestigationState(TypedDict):
    """
    Shared state container passed between LangGraph nodes during a forensic investigation.
    """
    ticker: str
    company_name: str
    raw_financials: Dict[str, Any]
    computed_metrics: Dict[str, Any]
    anomalies: List[Dict[str, Any]]
    selected_anomaly: Optional[Dict[str, Any]]
    hypothesis: Optional[str]
    prosecution_evidence: List[Dict[str, Any]]
    peer_evidence: List[Dict[str, Any]]
    defense_arguments: List[Dict[str, Any]]
    is_falsified: bool
    falsification_reason: Optional[str]
    evidence_strength: Optional[str]  # "Strong", "Moderate", "Weak"
    iteration_count: int
    current_anomaly_index: int
    contradiction_analysis: Optional[str]
    final_discovery: Optional[Dict[str, Any]]
    logs: List[str]
