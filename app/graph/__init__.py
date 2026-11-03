"""LangGraph workflow definition and state."""

from app.graph.state import ResearchState


def create_research_graph(*args, **kwargs):
    """Factory creating and compiling the multi-agent research graph."""
    from app.graph.workflow import create_research_graph as _create
    return _create(*args, **kwargs)


__all__ = ["ResearchState", "create_research_graph"]
