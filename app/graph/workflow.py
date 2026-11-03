"""LangGraph workflow assembly for autonomous literature review."""

from typing import Any, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    analyze_literature_node,
    check_critique_decision,
    critique_node,
    deduplicate_and_rank_node,
    dispatch_revision_tasks,
    dispatch_search_tasks,
    extract_evidence_node,
    planner_node,
    prepare_revision_node,
    retrieve_content_node,
    search_worker_node,
    synthesize_summary_node,
)
from app.graph.state import ResearchState


def create_research_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> Any:
    """Build and compile the multi-agent research StateGraph with Milestone 2 capabilities.

    Args:
        checkpointer: Optional checkpoint saver (e.g., MemorySaver or PostgresSaver).

    Returns:
        Compiled LangGraph instance.
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

    # Critique decision: route to revision loop or proceed to final synthesis
    workflow.add_conditional_edges(
        "critique",
        check_critique_decision,
        {
            "prepare_revision": "prepare_revision",
            "synthesize_summary": "synthesize_summary",
        },
    )

    # Dynamic fan-out for revision tasks -> search workers
    workflow.add_conditional_edges(
        "prepare_revision",
        dispatch_revision_tasks,
        ["search_worker"],
    )

    # Final report generation
    workflow.add_edge("synthesize_summary", END)

    # 3. Compile graph
    cp = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=cp)
