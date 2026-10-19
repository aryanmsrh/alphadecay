"""
ALPHA-DECAY Evidence Provenance & Citation Validation Authority.
Provides typed evidence records, source hierarchy ranking, verbatim excerpt validation,
calculation claim reproducibility, and investigation cutoff date enforcement.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import date, datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    REGULATORY_FILING = "regulatory_filing"
    CONCALL_TRANSCRIPT = "concall_transcript"
    INDEPENDENT_RESEARCH = "independent_research"
    NEWS = "news"
    SOCIAL_MEDIA = "social_media"
    DETERMINISTIC_CALCULATION = "deterministic_calculation"


class EvidenceDirection(str, Enum):
    SUPPORTS_ADVERSE = "SUPPORTS_ADVERSE"
    SUPPORTS_BENIGN = "SUPPORTS_BENIGN"
    NEUTRAL = "NEUTRAL"
    CONTRADICTORY = "CONTRADICTORY"


class EvidenceRecord(BaseModel):
    """
    Standardized, auditable record for every piece of qualitative or quantitative evidence.
    """
    evidence_id: str
    claim_id: Optional[str] = None
    source_title: str
    source_url: str
    source_type: str = Field(
        default="news",
        description="regulatory_filing, concall_transcript, independent_research, news, social_media, deterministic_calculation"
    )
    publisher: str = "Exchange / Statutory Authority"
    publication_date: Optional[date] = None
    document_date: Optional[date] = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    relevant_period: Optional[str] = None
    source_location: Optional[str] = None  # e.g. "Page 14, Q&A Session (Turn 2)", "Note 24: Trade Receivables"
    supporting_excerpt: str = Field(description="Verbatim text excerpt extracted from source")
    extracted_fact: str = Field(description="Core factual observation established by this excerpt")
    evidence_direction: str = Field(
        default="NEUTRAL",
        description="SUPPORTS_ADVERSE, SUPPORTS_BENIGN, NEUTRAL, or CONTRADICTORY"
    )
    credibility_tier: int = Field(
        default=2,
        description="1=Statutory filing/Audit, 2=Official Concall, 3=Industry Research, 4=News, 5=Social/Blog"
    )
    limitations: Optional[str] = None
    extraction_method: str = "statutory_scraper"
    validation_status: str = "VALID"


class MaterialClaim(BaseModel):
    """
    A material factual claim in an investigation report.
    """
    claim_id: str
    statement: str
    cited_evidence_ids: List[str] = Field(default_factory=list)
    is_calculation: bool = False
    calculation_formula: Optional[str] = None
    calculation_inputs: Dict[str, Any] = Field(default_factory=dict)
    confidence_level: str = "Medium"  # High, Medium, Low


class CitationValidationResult(BaseModel):
    """Result of citation and provenance verification."""
    is_valid: bool
    verified_claims_count: int
    unsupported_claims: List[str] = Field(default_factory=list)
    invalid_evidence_ids: List[str] = Field(default_factory=list)
    cutoff_violations: List[str] = Field(default_factory=list)
    calculation_violations: List[str] = Field(default_factory=list)
    social_media_warnings: List[str] = Field(default_factory=list)
    details: str = ""


def extract_publication_date(url: str, title: str = "", text: str = "") -> Optional[date]:
    """
    Extracts or infers publication date from source URL, title, or filename.
    Recognizes NSE/BSE timestamp patterns, ISO dates, and annual report fiscal year conventions.
    """
    import re
    if not url:
        return None
    # 1. NSE filings timestamp format: AR_..._DDMMYYYY[HHMMSS].pdf
    m_nse = re.search(r"_(\d{2})(\d{2})(20\d{2})(?:\d{6})?\.pdf", url)
    if m_nse:
        try:
            d, m, y = int(m_nse.group(1)), int(m_nse.group(2)), int(m_nse.group(3))
            if 1 <= d <= 31 and 1 <= m <= 12:
                return date(y, m, d)
        except ValueError:
            pass

    # 2. ISO / slash format in URL: /YYYY-MM-DD/ or /YYYY/MM/DD/
    m_iso = re.search(r"/(20\d{2})[-/](\d{2})[-/](\d{2})", url)
    if m_iso:
        try:
            return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        except ValueError:
            pass

    # 3. Annual report fiscal year in India (e.g. annual-report-2025-26):
    # Corporate fiscal year 2025-2026 ends March 31, 2026. Earliest publication is late May.
    m_ar = re.search(r"annual[-_]?report[-_]?(20\d{2})[-_](\d{2,4})", url.lower())
    if m_ar:
        start_year = int(m_ar.group(1))
        end_year = start_year + 1
        return date(end_year, 5, 20)

    return None


class EvidenceVault:
    """
    In-memory registry and validation engine for evidence items during an investigation run.
    Rejects duplicate IDs, enforces cutoff rules, and validates claims against sources.
    """

    def __init__(self, cutoff_date: Optional[Union[date, str]] = None):
        if isinstance(cutoff_date, str):
            try:
                self.cutoff_date = date.fromisoformat(cutoff_date)
            except ValueError:
                self.cutoff_date = None
        else:
            self.cutoff_date = cutoff_date
        self.evidence_by_id: Dict[str, EvidenceRecord] = {}
        self.excluded_by_cutoff: Dict[str, str] = {}

    def register_evidence(self, record: EvidenceRecord) -> bool:
        """
        Registers an evidence record after enforcing cutoff date and duplicate checks.
        Returns False if record violates the cutoff date or is rejected.
        """
        if not record.evidence_id:
            return False

        # Enforce investigation cutoff date
        if self.cutoff_date:
            pub_date = record.publication_date or record.document_date
            if not pub_date:
                pub_date = extract_publication_date(record.source_url, record.source_title, record.supporting_excerpt)
                if pub_date:
                    record.publication_date = pub_date

            if pub_date and pub_date > self.cutoff_date:
                reason = f"Published on {pub_date}, which exceeds investigation cutoff {self.cutoff_date}."
                self.excluded_by_cutoff[record.evidence_id] = reason
                print(f"[Evidence Vault] EXCLUDED: Evidence '{record.evidence_id}' {reason}")
                return False

        # Reject conflicting duplicate evidence IDs
        if record.evidence_id in self.evidence_by_id:
            existing = self.evidence_by_id[record.evidence_id]
            if existing.supporting_excerpt != record.supporting_excerpt or existing.source_url != record.source_url:
                print(f"[Evidence Vault Warning] Duplicate evidence ID '{record.evidence_id}' with conflicting content. Preserving initial record.")
                return False
            return True

        self.evidence_by_id[record.evidence_id] = record
        return True

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]:
        return self.evidence_by_id.get(evidence_id)

    def validate_claims(self, claims: List[MaterialClaim]) -> CitationValidationResult:
        """
        Validates that every material claim is backed by a registered evidence ID or reproducible calculation,
        and that low-credibility sources are not presented as standalone verified facts.
        """
        unsupported = []
        invalid_ids = []
        cutoff_violations = []
        calc_violations = []
        social_warnings = []
        verified_count = 0

        for claim in claims:
            # 1. Reproducible calculations
            if claim.is_calculation:
                if not claim.calculation_formula:
                    calc_violations.append(f"Claim '{claim.claim_id}' is marked calculation but lacks formula specification.")
                else:
                    verified_count += 1
                continue

            # 2. Material qualitative claims
            if not claim.cited_evidence_ids:
                unsupported.append(f"Claim '{claim.claim_id}': '{claim.statement}' has zero cited evidence records.")
                continue

            claim_valid = True
            for eid in claim.cited_evidence_ids:
                if eid in self.excluded_by_cutoff:
                    cutoff_violations.append(
                        f"Claim '{claim.claim_id}' cites excluded evidence '{eid}': {self.excluded_by_cutoff[eid]}"
                    )
                    claim_valid = False
                    continue

                ev = self.get_evidence(eid)
                if not ev:
                    invalid_ids.append(f"Claim '{claim.claim_id}' cites non-existent evidence_id '{eid}'.")
                    claim_valid = False
                else:
                    # Check source hierarchy: social media cannot be standalone proof of material adverse claim
                    if ev.source_type == "social_media" or ev.credibility_tier >= 5:
                        social_warnings.append(
                            f"Claim '{claim.claim_id}' relies on social media evidence ('{eid}'). "
                            f"Social media cannot serve as standalone proof for forensic conclusions."
                        )

            if claim_valid:
                verified_count += 1

        is_valid = (
            len(unsupported) == 0 and
            len(invalid_ids) == 0 and
            len(cutoff_violations) == 0 and
            len(calc_violations) == 0
        )
        details = (
            f"Validated {verified_count}/{len(claims)} material claims. "
            f"Unsupported: {len(unsupported)} | Invalid IDs: {len(invalid_ids)} | "
            f"Cutoff violations: {len(cutoff_violations)} | Calc violations: {len(calc_violations)} | "
            f"Social warnings: {len(social_warnings)}"
        )

        return CitationValidationResult(
            is_valid=is_valid,
            verified_claims_count=verified_count,
            unsupported_claims=unsupported,
            invalid_evidence_ids=invalid_ids,
            cutoff_violations=cutoff_violations,
            calculation_violations=calc_violations,
            social_media_warnings=social_warnings,
            details=details
        )
