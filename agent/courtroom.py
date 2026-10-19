"""
ALPHA-DECAY Adversarial Courtroom & Hypotheses Framework.
Defines competing hypotheses across operational, working capital, accounting, and industry dimensions,
adversarial roles (Prosecution, Defense, Adjudicator), and calibrated adjudication outcomes:
SUPPORTED, REFUTED, NOT_ESTABLISHED.
Enforces the core epistemological invariant: Failure to falsify is NOT confirmation.
"""

import re
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class AdjudicationVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class DataSufficiency(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    LIMITED = "LIMITED"
    INSUFFICIENT = "INSUFFICIENT"


def migrate_legacy_verdict(val: Any) -> str:
    """One-way migration helper from legacy verdict strings."""
    if not val:
        return AdjudicationVerdict.NOT_ESTABLISHED.value
    s = str(val).strip().upper()
    if s == "SUPPORTED":
        return AdjudicationVerdict.SUPPORTED.value
    if s in ("REFUTED", "FALSIFIED"):
        return AdjudicationVerdict.REFUTED.value
    if s in ("NOT_ESTABLISHED", "INCONCLUSIVE", "INSUFFICIENT_DATA"):
        return AdjudicationVerdict.NOT_ESTABLISHED.value
    return AdjudicationVerdict.NOT_ESTABLISHED.value


class HypothesisType(str, Enum):
    OPERATIONAL_CHANGE = "OPERATIONAL_CHANGE"
    PRICING_PRODUCT_MIX = "PRICING_PRODUCT_MIX"
    SEASONAL_TIMING = "SEASONAL_TIMING"
    WORKING_CAPITAL_CYCLE = "WORKING_CAPITAL_CYCLE"
    COST_INFLATION_OR_FX = "COST_INFLATION_OR_FX"
    ACCOUNTING_RECLASSIFICATION = "ACCOUNTING_RECLASSIFICATION"
    INDUSTRY_PEER_PARITY = "INDUSTRY_PEER_PARITY"
    DATA_QUALITY_OR_PARSING = "DATA_QUALITY_OR_PARSING"
    ADVERSE_STRUCTURAL = "ADVERSE_STRUCTURAL"


class Hypothesis(BaseModel):
    """
    Falsifiable hypothesis with explicit testable predictions.
    """
    hypothesis_id: str
    hypothesis_type: str = Field(
        default="OPERATIONAL_CHANGE",
        description="One of HypothesisType enums: OPERATIONAL_CHANGE, SEASONAL_TIMING, ADVERSE_STRUCTURAL, etc."
    )
    claim: str
    underlying_mechanism: str
    testable_predictions: List[str] = Field(default_factory=list)
    falsification_condition: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    confidence_assessment: str = "Unverified"  # High, Moderate, Low, Unverified


class AdversarialArguments(BaseModel):
    """Arguments prepared by Prosecution and Defense."""
    prosecution_argument: str = Field(description="Strongest evidence-based adverse case")
    prosecution_cited_evidence: List[str] = Field(default_factory=list)
    
    defense_counterargument: str = Field(description="Strongest evidence-based alternative/benign explanation")
    defense_cited_evidence: List[str] = Field(default_factory=list)
    
    unresolved_assumptions: List[str] = Field(default_factory=list)


class AdjudicationResult(BaseModel):
    """
    Final independent verdict reached by the Adjudicator.
    Evaluates underlying structured evidence and calculations, NOT just agent prose.
    """
    verdict: AdjudicationVerdict
    data_sufficiency: DataSufficiency = DataSufficiency.SUFFICIENT
    primary_hypothesis_evaluated: str
    adjudication_rationale: str
    decisive_evidence: List[str] = Field(default_factory=list)
    counter_evidence_considered: List[str] = Field(default_factory=list)
    missing_critical_data: List[str] = Field(default_factory=list)
    falsification_satisfied: bool = False
    calibrated_confidence: str  # "High", "Moderate", "Low"
    follow_up_observation_needed: str


class ForensicReportSchema(BaseModel):
    """
    Mandatory 8-Point Institutional Research Schema.
    Strictly validated via Pydantic with meaningful constraints.
    """
    finding_heading: str = Field(
        default="Verified Finding",
        description="Dynamic heading: 'Verified Finding', 'Quantitative Screening Signal', 'Refuted Hypothesis', 'Observed Fact (Causal Explanation Not Established)', or 'Zero Material Anomaly'"
    )
    discovery_1: str = Field(
        alias="1_The_Discovery",
        description="Exactly 1 sentence stating the verified reality, quantitative observation, or calibrated verdict"
    )
    why_it_matters_2: List[str] = Field(
        alias="2_Why_It_Matters",
        description="3 analytical bullet points on business, channel, and cash flow implications"
    )
    evidence_3: List[str] = Field(
        alias="3_Evidence",
        description="List of verified statutory/concall/audit URLs supporting the claims"
    )
    timeline_4: str = Field(
        alias="4_Timeline",
        description="Statutory reporting periods across which divergence emerged"
    )
    numbers_5: str = Field(
        alias="5_Numbers",
        description="Deterministic calculation figures (canonical DSRI, delta, margin wedge, peer spread)"
    )
    counterargument_6: str = Field(
        alias="6_Counterargument",
        description="Strongest alternative explanation from defense / macro / operational context"
    )
    falsification_condition_7: str = Field(
        alias="7_Falsification_Condition",
        description="Exact future metric normalization condition that disproves adverse hypothesis"
    )
    evidence_strength_8: str = Field(
        alias="8_Evidence_Strength",
        description="Calibrated adjudication rating: SUPPORTED, REFUTED, or NOT_ESTABLISHED with rationale"
    )
    methodology_and_limitations: Optional[str] = Field(
        default=None,
        description="Explicit note on data sources, heuristic formulas, or point-in-time limitations"
    )

    @field_validator("evidence_strength_8")
    @classmethod
    def validate_no_inconclusive(cls, v: str) -> str:
        if "INCONCLUSIVE" in v.upper():
            raise ValueError(
                "Obsolete verdict 'INCONCLUSIVE' is strictly forbidden. "
                "Use SUPPORTED, REFUTED, or NOT_ESTABLISHED."
            )
        return v

    @field_validator("discovery_1")
    @classmethod
    def validate_discovery_text(cls, v: str) -> str:
        if "INCONCLUSIVE" in v.upper():
            raise ValueError(
                "Obsolete verdict 'INCONCLUSIVE' is strictly forbidden in discovery. "
                "Use SUPPORTED, REFUTED, or NOT_ESTABLISHED."
            )
        return v

    @field_validator("why_it_matters_2")
    @classmethod
    def validate_why_it_matters(cls, v: List[str]) -> List[str]:
        if not v or len(v) < 1:
            raise ValueError("Why It Matters must contain at least 1 analytical bullet point.")
        return v[:5]  # Limit to max 5

    @field_validator("evidence_3")
    @classmethod
    def validate_evidence_urls(cls, v: List[str]) -> List[str]:
        if not v:
            return ["Statutory disclosures / Aggregator filings"]
        clean = []
        for item in v:
            s = str(item).strip()
            if s:
                clean.append(s)
        return clean or ["Statutory disclosures / Aggregator filings"]

    model_config = {"populate_by_name": True}
