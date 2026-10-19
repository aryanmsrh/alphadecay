from typing import TypedDict, List, Dict, Any, Optional

class InvestigationState(TypedDict):
    """
    Shared state container passed between LangGraph nodes during a forensic investigation.
    Maintains provenance, competing hypotheses across multiple dimensions,
    adversarial debate, calibrated verdicts, and multi-candidate investigation history.
    """
    run_id: str
    ticker: str
    company_name: str
    cutoff_date: Optional[str]
    raw_financials: Dict[str, Any]
    computed_metrics: Dict[str, Any]
    anomalies: List[Dict[str, Any]]
    selected_anomaly: Optional[Dict[str, Any]]
    no_material_anomaly: bool
    
    # Competing Hypotheses (Multi-class: Operational, Pricing/Mix, Timing, Working Capital, Adverse)
    competing_hypotheses: List[Dict[str, Any]]
    adverse_hypothesis: Optional[str]
    benign_hypothesis: Optional[str]
    
    # Evidence & Triangulation
    prosecution_evidence: List[Dict[str, Any]]
    peer_evidence: List[Dict[str, Any]]
    contradiction_analysis: Optional[str]
    
    # Adversarial Courtroom & Independent Adjudication
    adversarial_arguments: Optional[Dict[str, Any]]
    adjudication: Optional[Dict[str, Any]]
    is_falsified: bool
    falsification_reason: Optional[str]
    evidence_strength: Optional[str]  # "SUPPORTED", "REFUTED", "NOT_ESTABLISHED"
    data_sufficiency: Optional[str]   # "SUFFICIENT", "LIMITED", "INSUFFICIENT"
    adjudication_verdict: Optional[str]  # "SUPPORTED", "REFUTED", "NOT_ESTABLISHED"
    
    # Traversal, Multi-Candidate Tracking & Synthesis
    iteration_count: int
    current_anomaly_index: int
    max_anomalies_to_investigate: int
    completed_investigations: List[Dict[str, Any]]
    
    # Final Deliverable, Provenance & Validation Gate
    final_discovery: Optional[Dict[str, Any]]
    provider_metadata: Dict[str, Any]
    validation_passed: bool
    validation_report: Optional[Dict[str, Any]]
    logs: List[str]
