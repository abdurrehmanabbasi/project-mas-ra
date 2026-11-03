"""Unit tests for Literature Analyst Agent."""

from app.agents.analyst import AnalystAgent
from app.schemas.evidence import Evidence, PaperAnalysis
from app.schemas.papers import Paper


def test_analyst_synthesis_structure(sample_arxiv_paper, sample_s2_paper):
    """Verify AnalystAgent produces structured themes, comparisons, disagreements, and gaps."""
    analysis1 = PaperAnalysis(
        paper_id=sample_arxiv_paper.paper_id,
        methodology="Multi-agent cooperative game framework.",
        datasets_used=["SWE-bench", "HumanEval"],
        findings=["Improves task resolution by 24%."],
        limitations=["Token cost increases by 4x."],
    )
    analysis2 = PaperAnalysis(
        paper_id=sample_s2_paper.paper_id,
        methodology="Sequential prompt chaining with compiler feedback.",
        datasets_used=["HumanEval", "MBPP"],
        findings=["Single agent with compiler feedback rivals multi-agent accuracy with 60% fewer tokens."],
        limitations=["Fails on multi-file dependencies."],
    )

    ev1 = Evidence(
        paper_id=sample_arxiv_paper.paper_id,
        claim="Multi-agent improves SWE-bench.",
        supporting_passage="Experiments show a 24% improvement on SWE-bench.",
    )

    agent = AnalystAgent()
    synthesis = agent.analyze(
        question="How are multi-agent systems improving autonomous software engineering?",
        objective="Assess multi-agent architectures and benchmarks.",
        papers=[sample_arxiv_paper, sample_s2_paper],
        analyses=[analysis1, analysis2],
        evidence_records=[ev1],
    )

    # Check required synthesis elements
    assert len(synthesis.themes) >= 2
    assert len(synthesis.comparisons) >= 1
    assert len(synthesis.disagreements) >= 1
    assert len(synthesis.research_gaps) >= 1

    theme_names = [t["theme_name"] for t in synthesis.themes]
    assert any("Coordination" in n or "Empirical" in n for n in theme_names)

