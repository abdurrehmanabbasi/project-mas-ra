"""Integration tests for Milestone 3 trustworthy workflow with human-in-the-loop checkpoint interrupts."""

from unittest.mock import patch
from langgraph.types import Command
from app.graph.workflow import create_research_graph


def test_milestone3_interrupt_and_approve(sample_arxiv_paper):
    """Verify workflow pauses at human_review interrupt, saves checkpoint, and resumes on approval."""
    graph = create_research_graph()

    with patch(
        "app.tools.arxiv_search.ArxivSearchTool.search",
        return_value=[sample_arxiv_paper],
    ), patch(
        "app.tools.semantic_scholar.SemanticScholarTool.search",
        return_value=[],
    ), patch(
        "app.tools.paper_retriever.PaperRetriever.retrieve_pdf_bytes",
        return_value=None,
    ):
        initial_state = {
            "research_question": "How are multi-agent AI systems improving autonomous software engineering?",
            "scope": {
                "max_papers": 2,
                "preferred_sources": ["arxiv"],
                "skip_human_review": False,  # Enable interrupt
            },
        }

        thread_config = {"configurable": {"thread_id": "thread-hitl-approve"}}

        # 1. First invocation: executes up to human_review node and interrupts
        interrupted_output = graph.invoke(initial_state, config=thread_config)

        # Inspect checkpoint state
        state_snapshot = graph.get_state(thread_config)
        assert len(state_snapshot.tasks) > 0
        assert any(t.name == "human_review" for t in state_snapshot.tasks)

        # Verify review package was emitted in the interrupt
        interrupt_value = state_snapshot.tasks[0].interrupts[0].value
        assert "research_question" in interrupt_value
        assert "selected_papers_count" in interrupt_value
        assert "citation_checks" in interrupt_value

        # 2. Resume execution with approve decision via Command(resume=...)
        resume_command = Command(resume={"action": "approve", "feedback": "Looks comprehensive."})
        resumed_state = graph.invoke(resume_command, config=thread_config)

        # 3. Verify report was synthesized and run finalized
        assert resumed_state["human_approved"] is True
        assert resumed_state["status"] == "completed"
        assert "final_report" in resumed_state
        assert "title" in resumed_state["final_report"]


def test_milestone3_interrupt_and_reject(sample_arxiv_paper):
    """Verify workflow pauses at human_review interrupt and terminates with rejected status on reject decision."""
    graph = create_research_graph()

    with patch(
        "app.tools.arxiv_search.ArxivSearchTool.search",
        return_value=[sample_arxiv_paper],
    ), patch(
        "app.tools.semantic_scholar.SemanticScholarTool.search",
        return_value=[],
    ), patch(
        "app.tools.paper_retriever.PaperRetriever.retrieve_pdf_bytes",
        return_value=None,
    ):
        initial_state = {
            "research_question": "Irrelevant query to be rejected",
            "scope": {
                "max_papers": 1,
                "preferred_sources": ["arxiv"],
                "skip_human_review": False,
            },
        }

        thread_config = {"configurable": {"thread_id": "thread-hitl-reject"}}

        # Pause at interrupt
        graph.invoke(initial_state, config=thread_config)

        # Resume with reject decision
        reject_command = Command(resume={"action": "reject", "feedback": "Off-topic query."})
        final_state = graph.invoke(reject_command, config=thread_config)

        assert final_state["human_approved"] is False
        assert final_state["status"] == "rejected"
        assert "Rejected" in final_state["final_report"]["title"]


def test_milestone3_skip_human_review_mode(sample_arxiv_paper):
    """Verify skip_human_review=True runs without interruption for automated batch jobs."""
    graph = create_research_graph()

    with patch(
        "app.tools.arxiv_search.ArxivSearchTool.search",
        return_value=[sample_arxiv_paper],
    ), patch(
        "app.tools.semantic_scholar.SemanticScholarTool.search",
        return_value=[],
    ), patch(
        "app.tools.paper_retriever.PaperRetriever.retrieve_pdf_bytes",
        return_value=None,
    ):
        initial_state = {
            "research_question": "Autonomous batch research run",
            "scope": {
                "max_papers": 2,
                "preferred_sources": ["arxiv"],
                "skip_human_review": True,
            },
        }

        thread_config = {"configurable": {"thread_id": "thread-batch-run"}}
        final_state = graph.invoke(initial_state, config=thread_config)

        assert final_state["human_approved"] is True
        assert final_state["status"] == "completed"
        assert "final_report" in final_state

