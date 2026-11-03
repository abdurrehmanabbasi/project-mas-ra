"""LangGraph shared research state definition with custom reducers."""

from typing import Annotated, Any, Dict, List, Optional, TypedDict
import operator

from app.schemas.papers import Paper
from app.tools.paper_dedup import PaperDeduplicator


def merge_papers_reducer(
    existing: Optional[List[Dict[str, Any]]],
    new_items: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Reducer that combines and deduplicates paper dictionary records."""
    existing_list = existing or []
    new_list = new_items or []
    if not new_list:
        return existing_list
    if not existing_list:
        return new_list

    # Convert to Paper schemas for deterministic deduplication
    parsed_existing = [Paper.model_validate(p) for p in existing_list]
    parsed_new = [Paper.model_validate(p) for p in new_list]

    deduped = PaperDeduplicator.deduplicate(parsed_existing + parsed_new)
    return [p.model_dump() for p in deduped]


class ResearchState(TypedDict, total=False):
    """Global state flowing through the research workflow graph."""

    project_id: str
    research_question: str
    scope: Dict[str, Any]
    research_plan: Dict[str, Any]
    research_tasks: List[Dict[str, Any]]
    # Reducer accumulates and deduplicates search worker outputs
    search_results: Annotated[List[Dict[str, Any]], merge_papers_reducer]
    selected_papers: List[Dict[str, Any]]
    paper_contents: Annotated[List[Dict[str, Any]], operator.add]
    extracted_evidence: Annotated[List[Dict[str, Any]], operator.add]
    paper_analyses: Annotated[List[Dict[str, Any]], operator.add]
    synthesis: Dict[str, Any]
    critique: Dict[str, Any]
    verified_citations: List[Dict[str, Any]]
    review_package: Dict[str, Any]
    revision_count: int
    max_revisions: int
    human_approved: bool
    human_feedback: Optional[str]
    final_report: Dict[str, Any]
    errors: Annotated[List[str], operator.add]
    status: str

