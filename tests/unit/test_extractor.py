"""Unit tests for Evidence Extraction Agent."""

from app.agents.extractor import ExtractorAgent
from app.schemas.papers import Paper, PaperContent


def test_extractor_grounded_evidence(sample_arxiv_paper):
    """Verify extracted evidence contains verbatim passages and proper provenance."""
    sample_text = (
        "Abstract\n"
        "AgentBench evaluates LLMs across diverse interactive environments. "
        "Our experiments show that multi-agent systems achieve a 24.5% improvement on complex coding tasks. "
        "We evaluate on SWE-bench and HumanEval benchmarks. "
        "However, high token consumption and agent coordination overhead remain key limitations."
    )
    content = PaperContent(
        paper_id=sample_arxiv_paper.paper_id,
        text=sample_text,
        content_scope="full_text",
        retrieval_status="success",
    )

    agent = ExtractorAgent()
    analysis, evidence_items = agent.extract(sample_arxiv_paper, content)

    # Assert analysis populated
    assert analysis.paper_id == sample_arxiv_paper.paper_id
    assert len(analysis.findings) >= 1
    assert any("24.5%" in f or "improve" in f.lower() for f in analysis.findings)
    assert any("SWE-bench" in d or "Humaneval" in d for d in analysis.datasets_used)
    assert len(analysis.limitations) >= 1

    # Assert evidence records
    assert len(evidence_items) >= 1
    for ev in evidence_items:
        assert ev.paper_id == sample_arxiv_paper.paper_id
        assert ev.content_scope == "full_text"
        assert len(ev.supporting_passage) > 10
        # Verbatim quote must be present in source document
        assert ev.supporting_passage in sample_text


def test_extractor_abstract_only_scope(sample_s2_paper):
    """Verify evidence extracted from abstract preserves abstract_only scope."""
    content = PaperContent(
        paper_id=sample_s2_paper.paper_id,
        text=sample_s2_paper.abstract,
        content_scope="abstract_only",
        retrieval_status="success",
    )

    agent = ExtractorAgent()
    analysis, evidence_items = agent.extract(sample_s2_paper, content)

    assert len(evidence_items) >= 1
    for ev in evidence_items:
        assert ev.content_scope == "abstract_only"
        assert ev.supporting_passage in sample_s2_paper.abstract
