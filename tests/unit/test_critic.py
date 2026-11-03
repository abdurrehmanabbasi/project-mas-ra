"""Unit tests for Critic Agent and revision loop termination."""

from app.agents.critic import CriticAgent
from app.schemas.evidence import Critique, Evidence, ResearchSynthesis
from app.schemas.papers import Paper
from app.schemas.research import ResearchPlan, ResearchTask


def test_critic_approves_sufficient_coverage(sample_research_plan, sample_arxiv_paper, sample_s2_paper):
    """Verify CriticAgent approves when papers cover planned subquestions."""
    synthesis = ResearchSynthesis(
        themes=[{"theme_name": "Multi-Agent Systems", "paper_ids": [sample_arxiv_paper.paper_id]}],
        comparisons=[{"comparison_axis": "Accuracy", "observation": "Positive"}],
        research_gaps=["Contamination"],
    )

    critic = CriticAgent()
    critique = critic.evaluate(
        plan=sample_research_plan,
        papers=[sample_arxiv_paper, sample_s2_paper],
        evidence_records=[],
        synthesis=synthesis,
        revision_count=0,
        max_revisions=2,
    )

    assert isinstance(critique, Critique)
    assert critique.quality_score >= 0.70


def test_critic_requests_revision_when_topic_missing(sample_arxiv_paper):
    """Verify CriticAgent triggers revision when a planned subquestion is uncovered."""
    plan = ResearchPlan(
        research_question="What are the security vulnerabilities in autonomous code agents?",
        objective="Analyze prompt injection and code poisoning.",
        tasks=[
            ResearchTask(
                subquestion="How does prompt injection affect agent code generation?",
                query="prompt injection adversarial autonomous coding agents",
                keywords=["injection", "adversarial", "jailbreak", "security"],
            )
        ],
    )

    # Provided paper is on AgentBench evaluation, not prompt injection security
    unrelated_paper = Paper(
        title="AgentBench: Evaluating General LLMs",
        abstract="Benchmark evaluating game playing and web browsing.",
    )

    synthesis = ResearchSynthesis(themes=[], comparisons=[], research_gaps=[])

    critic = CriticAgent()
    critique = critic.evaluate(
        plan=plan,
        papers=[unrelated_paper],
        evidence_records=[],
        synthesis=synthesis,
        revision_count=0,
        max_revisions=2,
    )

    assert critique.needs_revision is True
    assert len(critique.suggested_revision_tasks) >= 1
    assert any("prompt injection" in t.lower() or "security" in t.lower() for t in critique.suggested_revision_tasks)


def test_critic_budget_limit_prevents_infinite_loop(sample_research_plan, sample_arxiv_paper):
    """Verify that reaching max_revisions forces needs_revision=False even with low coverage."""
    critic = CriticAgent()
    synthesis = ResearchSynthesis(themes=[], comparisons=[], research_gaps=[])

    critique = critic.evaluate(
        plan=sample_research_plan,
        papers=[sample_arxiv_paper],
        evidence_records=[],
        synthesis=synthesis,
        revision_count=2,  # Budget exhausted
        max_revisions=2,
    )

    assert critique.needs_revision is False
    assert critique.suggested_revision_tasks == []

