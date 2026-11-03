"""Unit tests for Citation and Claim Verification engine."""

from app.schemas.evidence import Evidence
from app.schemas.papers import Paper, PaperSource
from app.tools.citation_verifier import CitationVerifier


def test_validate_doi_valid_and_invalid():
    """Verify DOI syntax checking handles valid, invalid, and prefixed formats."""
    assert CitationVerifier.validate_doi("10.1145/3611643.3616265") is True
    assert CitationVerifier.validate_doi("10.48550/arXiv.2308.03688") is True
    assert CitationVerifier.validate_doi("https://doi.org/10.1007/s10515-021-00288-7") is True
    assert CitationVerifier.validate_doi("doi:10.1016/j.artint.2023.103980") is True

    # Invalid DOIs
    assert CitationVerifier.validate_doi("invalid-doi-123") is False
    assert CitationVerifier.validate_doi("10.123") is False
    assert CitationVerifier.validate_doi(None) is False
    assert CitationVerifier.validate_doi("") is False


def test_validate_url_valid_and_invalid():
    """Verify URL syntax validation."""
    assert CitationVerifier.validate_url("https://arxiv.org/abs/2308.03688") is True
    assert CitationVerifier.validate_url("http://example.com/paper.pdf") is True
    assert CitationVerifier.validate_url("ftp://not-http.org") is False
    assert CitationVerifier.validate_url("just-a-string") is False
    assert CitationVerifier.validate_url(None) is False


def test_verify_claim_support_grounded():
    """Verify claim support check succeeds when grounded passage is present."""
    ev = Evidence(
        paper_id="paper-1",
        claim="Pass@1 increased by 20%.",
        supporting_passage="The multi-agent system increased pass@1 by 20% on HumanEval.",
    )
    supported, notes = CitationVerifier.verify_claim_support(
        paper_id="paper-1",
        claim="Pass@1 increased by 20%.",
        evidence_records=[ev],
    )
    assert supported is True
    assert notes is None


def test_verify_claim_support_ungrounded():
    """Verify claim support check fails and notes reason when paper lacks evidence."""
    supported, notes = CitationVerifier.verify_claim_support(
        paper_id="paper-2",
        claim="Pass@1 increased by 20%.",
        evidence_records=[],  # No evidence
    )
    assert supported is False
    assert "no extracted evidence" in notes.lower()


def test_verify_all(sample_arxiv_paper):
    """Verify verify_all executes across paper corpus."""
    ev = Evidence(
        paper_id=sample_arxiv_paper.paper_id,
        claim="AgentBench benchmark.",
        supporting_passage="AgentBench evaluates autonomous agents across tasks.",
    )
    checks = CitationVerifier.verify_all(
        papers=[sample_arxiv_paper],
        evidence_records=[ev],
    )
    assert len(checks) == 1
    c = checks[0]
    assert c.paper_id == sample_arxiv_paper.paper_id
    assert c.doi_valid is True
    assert c.url_accessible is True
    assert c.claim_supported is True
    assert c.notes is None

