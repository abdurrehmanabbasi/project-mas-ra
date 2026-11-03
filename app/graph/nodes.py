"""Graph nodes executing research planning, parallel retrieval, and synthesis."""

import logging
from typing import Any, Dict, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Send

from app.agents.planner import PlannerAgent
from app.config import get_settings
from app.graph.prompts import WRITER_SYSTEM_PROMPT, WRITER_USER_TEMPLATE
from app.graph.state import ResearchState
from app.schemas.papers import Paper
from app.schemas.research import ResearchScope
from app.tools.arxiv_search import ArxivSearchTool
from app.tools.paper_dedup import PaperDeduplicator
from app.tools.semantic_scholar import SemanticScholarTool

logger = logging.getLogger(__name__)


def planner_node(state: ResearchState) -> Dict[str, Any]:
    """Execute Planner Agent to generate structured research plan and tasks."""
    question = state.get("research_question", "")
    raw_scope = state.get("scope", {})
    scope = ResearchScope.model_validate(raw_scope) if raw_scope else ResearchScope()

    planner = PlannerAgent()
    plan = planner.plan(question=question, scope=scope)

    return {
        "research_plan": plan.model_dump(),
        "research_tasks": [t.model_dump() for t in plan.tasks],
        "status": "planned",
    }


def dispatch_search_tasks(state: ResearchState) -> List[Send]:
    """Fan-out dynamic edge dispatching parallel search workers for each subquestion."""
    tasks = state.get("research_tasks", [])
    raw_scope = state.get("scope", {})

    send_list: List[Send] = []
    for task in tasks:
        payload = {
            "task": task,
            "scope": raw_scope,
        }
        send_list.append(Send("search_worker", payload))

    return send_list


def search_worker_node(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Worker node querying academic providers for a single research task."""
    task = payload.get("task", {})
    raw_scope = payload.get("scope", {})

    query = task.get("query", "")
    scope = ResearchScope.model_validate(raw_scope) if raw_scope else ResearchScope()

    date_range = (scope.date_range_start, scope.date_range_end)
    papers: List[Paper] = []

    # Query arXiv if enabled in scope
    if "arxiv" in scope.preferred_sources:
        arxiv_tool = ArxivSearchTool()
        arxiv_papers = arxiv_tool.search(
            query=query,
            max_results=get_settings().MAX_PAPERS_PER_TASK,
            date_range=date_range,
        )
        papers.extend(arxiv_papers)

    # Query Semantic Scholar if enabled in scope
    if "semantic_scholar" in scope.preferred_sources:
        s2_tool = SemanticScholarTool()
        s2_papers = s2_tool.search(
            query=query,
            max_results=get_settings().MAX_PAPERS_PER_TASK,
            date_range=date_range,
        )
        papers.extend(s2_papers)

    # Return results (state reducer will merge and deduplicate across parallel workers)
    return {
        "search_results": [p.model_dump() for p in papers],
    }


def deduplicate_and_rank_node(state: ResearchState) -> Dict[str, Any]:
    """Deduplicate all parallel worker results and rank by relevance and recency."""
    raw_results = state.get("search_results", [])
    raw_scope = state.get("scope", {})
    scope = ResearchScope.model_validate(raw_scope) if raw_scope else ResearchScope()

    parsed = [Paper.model_validate(p) for p in raw_results]
    deduped = PaperDeduplicator.deduplicate(parsed)

    # Sort papers by reported citation count (desc) and year (desc)
    def rank_key(p: Paper) -> tuple:
        return (p.year or 0, p.citation_count or 0)

    deduped.sort(key=rank_key, reverse=True)

    # Limit to target paper count
    selected = deduped[: scope.max_papers]

    return {
        "selected_papers": [p.model_dump() for p in selected],
        "status": "papers_selected",
    }


def synthesize_summary_node(state: ResearchState) -> Dict[str, Any]:
    """Synthesize structured literature review report from selected papers."""
    settings = get_settings()
    question = state.get("research_question", "")
    plan = state.get("research_plan", {})
    selected_dicts = state.get("selected_papers", [])

    # Format paper summaries for the writer prompt
    paper_summaries: List[str] = []
    references: List[Dict[str, Any]] = []

    for i, p_data in enumerate(selected_dicts):
        p = Paper.model_validate(p_data)
        authors_str = ", ".join(p.authors[:3]) + (" et al." if len(p.authors) > 3 else "")
        entry = (
            f"[{i+1}] {p.title} ({authors_str}, {p.year or 'n.d.'})\n"
            f"Abstract: {p.abstract[:300] if p.abstract else 'No abstract available'}...\n"
        )
        paper_summaries.append(entry)
        references.append({
            "index": i + 1,
            "title": p.title,
            "authors": p.authors,
            "year": p.year,
            "doi": p.doi,
            "sources": [s.model_dump() for s in p.sources],
        })

    summary_text = "\n".join(paper_summaries)
    llm = None
    if settings.OPENAI_API_KEY:
        llm = ChatOpenAI(model=settings.OPENAI_MODEL_NAME, api_key=settings.OPENAI_API_KEY)

    report_content = ""
    if llm is not None and selected_dicts:
        try:
            prompt_content = WRITER_USER_TEMPLATE.format(
                research_question=question,
                objective=plan.get("objective", ""),
                paper_count=len(selected_dicts),
                papers_summary=summary_text,
            )
            response = llm.invoke([
                SystemMessage(content=WRITER_SYSTEM_PROMPT),
                HumanMessage(content=prompt_content),
            ])
            report_content = response.content
        except Exception as e:
            logger.error(f"Writer LLM error: {e}", exc_info=True)

    # Heuristic report generator if LLM not present or failed
    if not report_content:
        report_content = (
            f"# Literature Review: {question}\n\n"
            f"## Objective\n{plan.get('objective', '')}\n\n"
            f"## Identified Papers ({len(selected_dicts)} Selected)\n"
        )
        for ref in references:
            authors_str = ", ".join(ref['authors'][:3]) if ref['authors'] else "Unknown"
            report_content += f"- **{ref['title']}** ({authors_str}, {ref['year'] or 'n.d.'})\n"

    final_report = {
        "title": f"Literature Review: {question}",
        "research_question": question,
        "objective": plan.get("objective", ""),
        "content_markdown": report_content,
        "selected_papers_count": len(selected_dicts),
        "references": references,
    }

    return {
        "final_report": final_report,
        "status": "completed",
    }

