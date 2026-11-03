"""Unit tests for Evaluation Metrics Calculator."""

import pytest
from app.evaluation.metrics import MetricsCalculator
from app.schemas.evidence import Evidence
from app.schemas.report import CitationCheck, ReportSection, ResearchReport


def test_citation_evaluation_metrics():
    """Verify calculation of DOI validity and claim support percentages."""
    checks = [
        CitationCheck(citation_id="c1", paper_id="p1", doi_valid=True, url_accessible=True, claim_supported=True),
        CitationCheck(citation_id="c2", paper_id="p2", doi_valid=True, url_accessible=True, claim_supported=False),
        CitationCheck(citation_id="c3", paper_id="p3", doi_valid=False, url_accessible=True, claim_supported=True),
    ]

    res = MetricsCalculator.evaluate_citations(checks)
    assert res.total_citations == 3
    assert res.valid_dois_count == 2
    assert res.supported_claims_count == 2
    assert res.doi_validity_rate == pytest.approx(0.6667, 0.001)
    assert res.claim_support_rate == pytest.approx(0.6667, 0.001)


def test_evidence_grounding_metrics():
    """Verify calculation of full-text ratio and grounded passage ratio."""
    records = [
        Evidence(
            evidence_id="e1",
            paper_id="p1",
            claim="Claim 1",
            supporting_passage="This is an exact verbatim passage from the paper body.",
            content_scope="full_text",
            extraction_confidence=0.9,
        ),
        Evidence(
            evidence_id="e2",
            paper_id="p2",
            claim="Claim 2",
            supporting_passage="Another valid supporting passage from abstract.",
            content_scope="abstract_only",
            extraction_confidence=0.8,
        ),
    ]

    res = MetricsCalculator.evaluate_evidence(records)
    assert res.total_evidence_records == 2
    assert res.full_text_count == 1
    assert res.abstract_only_count == 1
    assert res.full_text_ratio == 0.5
    assert res.grounded_passage_ratio == 1.0


def test_topic_coverage_metrics():
    """Verify topic coverage against target benchmark dimensions."""
    report_text = (
        "This systematic review analyzes multi-agent coordination architectures and "
        "evaluates empirical benchmarks such as SWE-bench, measuring execution latency overhead."
    )
    targets = [
        "Multi-agent coordination",
        "Empirical benchmarks",
        "Hardware quantization and tensor parallelism",
    ]

    res = MetricsCalculator.evaluate_coverage(report_text, targets)
    assert res.target_topics_count == 3
    assert res.covered_topics_count == 2
    assert "Hardware quantization and tensor parallelism" in res.missing_topics
    assert res.coverage_score == pytest.approx(0.6667, 0.001)

