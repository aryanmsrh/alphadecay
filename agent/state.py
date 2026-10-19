from typing import TypedDict, List, Dict, Any, Optional


class NodalRound(TypedDict):
    round_index: int
    anomaly_title: str
    anomaly_description: str
    hypothesis: str
    attacker_case: str
    defender_case: str
    verdict: str
    strength_score: int
    verdict_reason: str


class InvestigationState(TypedDict):
    run_id: str
    ticker: str
    company_name: str
    headline_hypothesis: str
    indicators: Dict[str, Any]
    evidence_items: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    current_anomaly_index: int
    current_anomaly: Optional[Dict[str, Any]]
    current_hypothesis: Optional[str]
    current_attacker_case: Optional[str]
    current_defender_case: Optional[str]
    nodal_flow: List[NodalRound]
    final_verdict: str
    final_strength: int
    final_summary: str
    final_result_hypothesis: str
    provider_used: str
