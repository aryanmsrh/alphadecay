import pytest
from datetime import date
from agent.evidence import EvidenceRecord, MaterialClaim, EvidenceVault

def test_evidence_vault_registration_and_lookup():
    vault = EvidenceVault()
    rec = EvidenceRecord(
        evidence_id="EV-001",
        source_title="BSE Statutory Concall Transcript",
        source_url="https://www.bseindia.com/filing.pdf",
        source_type="regulatory_filing",
        supporting_excerpt="Trade receivables increased due to extended credit terms.",
        extracted_fact="Company extended credit terms to distributors in Q4.",
        credibility_tier=1
    )
    assert vault.register_evidence(rec) is True
    assert vault.get_evidence("EV-001") is not None
    assert vault.get_evidence("EV-999") is None

def test_cutoff_date_enforcement():
    cutoff = date(2025, 12, 31)
    vault = EvidenceVault(cutoff_date=cutoff)

    # Valid record published before cutoff
    rec_valid = EvidenceRecord(
        evidence_id="EV-VALID",
        source_title="Q2 FY26 Earnings Call",
        source_url="https://example.com/q2.pdf",
        source_type="regulatory_filing",
        publication_date=date(2025, 11, 15),
        supporting_excerpt="Valid text",
        extracted_fact="Fact"
    )
    assert vault.register_evidence(rec_valid) is True

    # Invalid record published after cutoff
    rec_post_cutoff = EvidenceRecord(
        evidence_id="EV-FUTURE",
        source_title="Q4 FY26 Results",
        source_url="https://example.com/q4.pdf",
        source_type="regulatory_filing",
        publication_date=date(2026, 4, 15),
        supporting_excerpt="Future text",
        extracted_fact="Fact"
    )
    assert vault.register_evidence(rec_post_cutoff) is False
    assert vault.get_evidence("EV-FUTURE") is None

def test_duplicate_evidence_id_conflict_rejection():
    vault = EvidenceVault()
    rec1 = EvidenceRecord(
        evidence_id="EV-DUP",
        source_title="Source 1",
        source_url="https://example.com/1.pdf",
        supporting_excerpt="Original text",
        extracted_fact="Fact 1"
    )
    assert vault.register_evidence(rec1) is True

    # Conflicting duplicate
    rec2 = EvidenceRecord(
        evidence_id="EV-DUP",
        source_title="Source 2",
        source_url="https://example.com/2.pdf",
        supporting_excerpt="Conflicting text",
        extracted_fact="Fact 2"
    )
    assert vault.register_evidence(rec2) is False
    # Preserved original
    assert vault.get_evidence("EV-DUP").supporting_excerpt == "Original text"

def test_citation_validator_detects_unsupported_and_invalid_claims():
    cutoff = date(2025, 12, 31)
    vault = EvidenceVault(cutoff_date=cutoff)
    vault.register_evidence(EvidenceRecord(
        evidence_id="EV-100",
        source_title="Statutory Note",
        source_url="https://screener.in",
        source_type="regulatory_filing",
        publication_date=date(2025, 6, 1),
        supporting_excerpt="Debtor days elongated by 3 days.",
        extracted_fact="Debtor days +3d",
        credibility_tier=1
    ))
    # Post-cutoff record (will be excluded)
    vault.register_evidence(EvidenceRecord(
        evidence_id="EV-POST",
        source_title="Post Cutoff",
        source_url="https://screener.in",
        publication_date=date(2026, 2, 1),
        supporting_excerpt="Post cutoff text",
        extracted_fact="Post cutoff fact"
    ))

    claims = [
        # Valid claim referencing existing evidence
        MaterialClaim(claim_id="C-1", statement="Debtor days widened.", cited_evidence_ids=["EV-100"]),
        # Claim with broken/non-existent evidence ID
        MaterialClaim(claim_id="C-2", statement="Inventory piled up.", cited_evidence_ids=["EV-DOES-NOT-EXIST"]),
        # Unsupported claim with no citations
        MaterialClaim(claim_id="C-3", statement="Company is losing pricing power.", cited_evidence_ids=[]),
        # Valid calculation claim
        MaterialClaim(claim_id="C-4", statement="YoY growth is 15%.", is_calculation=True, calculation_formula="(115-100)/100*100"),
        # Invalid calculation claim (missing formula)
        MaterialClaim(claim_id="C-5", statement="Bad calc.", is_calculation=True, calculation_formula=None),
        # Claim citing excluded post-cutoff evidence
        MaterialClaim(claim_id="C-6", statement="Future event.", cited_evidence_ids=["EV-POST"])
    ]

    val_res = vault.validate_claims(claims)
    assert val_res.is_valid is False
    assert val_res.verified_claims_count == 2 # C-1 and C-4
    assert any("C-2" in item for item in val_res.invalid_evidence_ids)
    assert any("C-3" in item for item in val_res.unsupported_claims)
    assert any("C-5" in item for item in val_res.calculation_violations)
    assert any("C-6" in item for item in val_res.cutoff_violations)

def test_social_media_source_generates_warning():
    vault = EvidenceVault()
    vault.register_evidence(EvidenceRecord(
        evidence_id="EV-TWITTER",
        source_title="Twitter Thread on Channel Stuffing",
        source_url="https://x.com/analyst/status/123",
        source_type="social_media",
        supporting_excerpt="Heard from dealers that goods are being pushed.",
        extracted_fact="Dealer hearsay",
        credibility_tier=5
    ))

    claims = [
        MaterialClaim(claim_id="C-SOCIAL", statement="Channel stuffing occurring.", cited_evidence_ids=["EV-TWITTER"])
    ]
    val_res = vault.validate_claims(claims)
    assert len(val_res.social_media_warnings) > 0
    assert "social media" in val_res.social_media_warnings[0].lower()
