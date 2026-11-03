"""LangGraph workflow assembly for autonomous literature review."""

from typing import Any, Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    deduplicate_and_rank_node,
    dispatch_search_tasks,
    planner_node,
    search_worker_node,
    synthesize_summary_node,
)
from app.graph.state import ResearchState


def create_research_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> Any:
    """Build and compile the multi-agent research StateGraph.

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
    workflow.add_node("synthesize_summary", synthesize_summary_node)

    # 2. Add edges
    workflow.add_edge(START, "planner")

    # Dynamic fan-out: planner produces N research tasks -> dispatches N parallel search workers
    workflow.add_conditional_edges(
        "planner",
        dispatch_search_tasks,
        ["search_worker"],
    )

    # Fan-in: parallel search workers merge results into state -> rank & deduplicate
    workflow.add_edge("search_worker", "deduplicate_and_rank")
    workflow.add_edge("deduplicate_and_rank", "synthesize_summary")
    workflow.add_edge("synthesize_summary", END)

    # 3. Compile graph
    # If no checkpointer provided, default to in-memory checkpointer for developer agility
    cp = checkpointer if checkpointer is not None else MemorySaver()
    return workflow.compile(checkpointer=cp)

