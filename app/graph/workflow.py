"""LangGraph workflow assembly for autonomous literature review (Milestone 3)."""

from typing import Any, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.database.checkpointer import get_checkpointer
from app.graph.nodes import (
    analyze_literature_node,
    check_critique_decision,
    check_human_decision,
    critique_node,
    deduplicate_and_rank_node,
    dispatch_human_revision_tasks,
    dispatch_revision_tasks,
    dispatch_search_tasks,
    extract_evidence_node,
    human_review_node,
    mark_rejected_node,
    planner_node,
    prepare_human_revision_node,
    prepare_revision_node,
    retrieve_content_node,
    search_worker_node,
    synthesize_summary_node,
    verify_citations_node,
)
from app.graph.state import ResearchState


def create_research_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> Any:
    """Build and compile the multi-agent research StateGraph with Milestone 3 trustworthy workflow.

    Args:
        checkpointer: Optional checkpoint saver (defaults to get_checkpointer()).

    Returns:
        Compiled LangGraph instance with interrupt capability.
    """
    workflow = StateGraph(ResearchState)

    # 1. Add functional nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("search_worker", search_worker_node)
    workflow.add_node("deduplicate_and_rank", deduplicate_and_rank_node)
    workflow.add_node("retrieve_content", retrieve_content_node)
    workflow.add_node("extract_evidence", extract_evidence_node)
    workflow.add_node("analyze_literature", analyze_literature_node)
    workflow.add_node("critique", critique_node)
    workflow.add_node("prepare_revision", prepare_revision_node)
    workflow.add_node("verify_citations", verify_citations_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("prepare_human_revision", prepare_human_revision_node)
    workflow.add_node("mark_rejected", mark_rejected_node)
    workflow.add_node("synthesize_summary", synthesize_summary_node)

    # 2. Add structural edges
    workflow.add_edge(START, "planner")

    # Dynamic fan-out: planner produces N research tasks -> dispatches N parallel search workers
    workflow.add_conditional_edges(
        "planner",
        dispatch_search_tasks,
        ["search_worker"],
    )

    # Fan-in: parallel search workers merge results into state -> rank & deduplicate
    workflow.add_edge("search_worker", "deduplicate_and_rank")

    # Phase 5: Retrieve PDF content where accessible; fallback to abstract
    workflow.add_edge("deduplicate_and_rank", "retrieve_content")

    # Phase 6: Extract atomic evidence records and structured analyses
    workflow.add_edge("retrieve_content", "extract_evidence")

    # Phase 7: Cross-paper comparative analysis and thematic clustering
    workflow.add_edge("extract_evidence", "analyze_literature")

    # Phase 8: Critique literature coverage and empirical gaps
    workflow.add_edge("analyze_literature", "critique")

    # Automated critique loop: route to automated revision or proceed to citation verification
    workflow.add_conditional_edges(
        "critique",
        check_critique_decision,
        {
            "prepare_revision": "prepare_revision",
            "verify_citations": "verify_citations",
        },
    )

    # Automated revision dynamic fan-out -> search workers
    workflow.add_conditional_edges(
        "prepare_revision",
        dispatch_revision_tasks,
        ["search_worker"],
    )

    # Phase 9: Verify bibliographic metadata and claim grounding
    workflow.add_edge("verify_citations", "human_review")

    # Phase 10: Human review decision routing (approve, request revision, or reject)
    workflow.add_conditional_edges(
        "human_review",
        check_human_decision,
        {
            "synthesize_summary": "synthesize_summary",
            "prepare_human_revision": "prepare_human_revision",
            "mark_rejected": "mark_rejected",
        },
    )

    # Human-requested revision dynamic fan-out -> search workers
    workflow.add_conditional_edges(
        "prepare_human_revision",
        dispatch_human_revision_tasks,
        ["search_worker"],
    )

    # Final report generation and termination
    workflow.add_edge("synthesize_summary", END)
    workflow.add_edge("mark_rejected", END)

    # 3. Compile graph with checkpointer
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    return workflow.compile(checkpointer=cp)
