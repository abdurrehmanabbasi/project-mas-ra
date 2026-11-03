"""Integration test for the complete Milestone 1 LangGraph research pipeline."""

from unittest.mock import patch
from app.graph.workflow import create_research_graph
from app.schemas.papers import Paper, PaperSource


def test_complete_milestone1_research_pipeline(sample_arxiv_paper, sample_s2_paper):
    """Verify end-to-end execution of Milestone 1 research workflow graph."""
    graph = create_research_graph()

    # Mock tool search calls so the integration test runs offline and deterministically
    with patch(
        "app.tools.arxiv_search.ArxivSearchTool.search",
        return_value=[sample_arxiv_paper],
    ), patch(
        "app.tools.semantic_scholar.SemanticScholarTool.search",
        return_value=[sample_s2_paper],
    ):
        initial_state = {
            "research_question": "How are multi-agent AI systems improving autonomous software engineering?",
            "scope": {
                "max_papers": 5,
                "preferred_sources": ["arxiv", "semantic_scholar"],
                "date_range_start": 2020,
                "date_range_end": 2026,
            },
        }

        # Execute graph with thread config for checkpointer
        config = {"configurable": {"thread_id": "test-thread-001"}}
        final_state = graph.invoke(initial_state, config=config)

    # 1. Assert planning completed
    assert "research_plan" in final_state
    plan = final_state["research_plan"]
    assert "tasks" in plan
    assert len(plan["tasks"]) >= 2

    # 2. Assert search results gathered and deduplicated
    assert "selected_papers" in final_state
    selected = final_state["selected_papers"]
    assert len(selected) >= 1

    # In our mock, both sample papers are duplicates of AgentBench, so deduplication should yield 1 paper
    assert len(selected) == 1
    paper = selected[0]
    assert "AgentBench" in paper["title"]
    # Check that sources from both providers were merged into the single paper
    providers = {s["provider"] for s in paper["sources"]}
    assert "arxiv" in providers
    assert "semantic_scholar" in providers

    # 3. Assert final report produced
    assert "final_report" in final_state
    report = final_state["final_report"]
    assert "title" in report
    assert "content_markdown" in report
    assert len(report["content_markdown"]) > 50
    assert len(report["references"]) == 1
    assert final_state["status"] == "completed"

