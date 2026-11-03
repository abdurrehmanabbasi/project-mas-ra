"""Integration tests for the complete Milestone 2 evidence-grounded research pipeline."""

from unittest.mock import MagicMock, patch
from app.graph.workflow import create_research_graph
from app.schemas.evidence import Critique
from app.schemas.papers import Paper, PaperSource


def test_milestone2_end_to_end_pipeline(sample_arxiv_paper, sample_s2_paper):
    """Verify complete Milestone 2 execution with retrieval, extraction, analysis, and critique."""
    graph = create_research_graph()

    # Mock tool search calls
    with patch(
        "app.tools.arxiv_search.ArxivSearchTool.search",
        return_value=[sample_arxiv_paper],
    ), patch(
        "app.tools.semantic_scholar.SemanticScholarTool.search",
        return_value=[sample_s2_paper],
    ), patch(
        "app.tools.paper_retriever.PaperRetriever.retrieve_pdf_bytes",
        return_value=None,  # Fallback gracefully to abstract_only
    ):
        initial_state = {
            "research_question": "How are multi-agent AI systems improving autonomous software engineering?",
            "scope": {
                "max_papers": 3,
                "preferred_sources": ["arxiv", "semantic_scholar"],
                "date_range_start": 2020,
                "date_range_end": 2026,
            },
        }

        config = {"configurable": {"thread_id": "test-milestone2-thread"}}
        final_state = graph.invoke(initial_state, config=config)

    # 1. Assert content retrieval
    assert "paper_contents" in final_state
    contents = final_state["paper_contents"]
    assert len(contents) >= 1
    assert any(c["content_scope"] == "abstract_only" for c in contents)

    # 2. Assert evidence extraction
    assert "extracted_evidence" in final_state
    evidence = final_state["extracted_evidence"]
    assert len(evidence) >= 1
    assert all("supporting_passage" in e for e in evidence)

    # 3. Assert cross-paper synthesis
    assert "synthesis" in final_state
    synthesis = final_state["synthesis"]
    assert "themes" in synthesis
    assert len(synthesis["themes"]) >= 1
    assert "comparisons" in synthesis
    assert len(synthesis["comparisons"]) >= 1

    # 4. Assert critic evaluation
    assert "critique" in final_state
    critique = final_state["critique"]
    assert "quality_score" in critique

    # 5. Assert final synthesis report
    assert "final_report" in final_state
    report = final_state["final_report"]
    assert "title" in report
    assert "content_markdown" in report
    assert "Thematic Synthesis" in report["content_markdown"]
    assert "Key Grounded Evidence" in report["content_markdown"]
    assert final_state["status"] == "completed"


def test_milestone2_critic_revision_loop(sample_arxiv_paper):
    """Verify that a critique requiring revision loops back to search and increments revision_count."""
    graph = create_research_graph()

    # Create a mock critic that requests revision on cycle 0, then approves on cycle 1
    eval_call_count = 0

    def mock_critic_evaluate(*args, **kwargs):
        nonlocal eval_call_count
        eval_call_count += 1
        if eval_call_count == 1:
            return Critique(
                quality_score=0.50,
                missing_topics=["Security vulnerabilities in multi-agent code execution"],
                needs_revision=True,
                suggested_revision_tasks=["multi-agent code execution security vulnerabilities"],
            )
        return Critique(
            quality_score=0.85,
            missing_topics=[],
            needs_revision=False,
            suggested_revision_tasks=[],
        )

    with patch(
        "app.tools.arxiv_search.ArxivSearchTool.search",
        return_value=[sample_arxiv_paper],
    ), patch(
        "app.tools.semantic_scholar.SemanticScholarTool.search",
        return_value=[],
    ), patch(
        "app.tools.paper_retriever.PaperRetriever.retrieve_pdf_bytes",
        return_value=None,
    ), patch(
        "app.agents.critic.CriticAgent.evaluate",
        side_effect=mock_critic_evaluate,
    ):
        initial_state = {
            "research_question": "What are multi-agent software engineering architectures and their security risks?",
            "scope": {
                "max_papers": 3,
                "preferred_sources": ["arxiv"],
            },
            "revision_count": 0,
            "max_revisions": 2,
        }

        config = {"configurable": {"thread_id": "test-revision-thread"}}
        final_state = graph.invoke(initial_state, config=config)

    # Verify that the critic evaluated twice (initial cycle + revision cycle)
    assert eval_call_count == 2
    assert final_state["revision_count"] == 1
    assert final_state["status"] == "completed"

