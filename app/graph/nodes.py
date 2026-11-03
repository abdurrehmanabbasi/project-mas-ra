"""Graph nodes executing research planning, retrieval, extraction, critique, and human review."""

import logging
import uuid
from typing import Any, Dict, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Send, interrupt

from app.agents.analyst import AnalystAgent
from app.agents.critic import CriticAgent
from app.agents.extractor import ExtractorAgent
from app.agents.planner import PlannerAgent
from app.config import get_settings
from app.graph.prompts import WRITER_SYSTEM_PROMPT, WRITER_USER_TEMPLATE
from app.graph.state import ResearchState
from app.schemas.evidence import Evidence, PaperAnalysis, ResearchSynthesis
from app.schemas.papers import Paper, PaperContent
from app.schemas.report import CitationCheck, ReviewPackage
from app.schemas.research import ResearchPlan, ResearchScope, ResearchTask
from app.tools.arxiv_search import ArxivSearchTool
from app.tools.citation_verifier import CitationVerifier
from app.tools.paper_dedup import PaperDeduplicator
from app.tools.paper_retriever import PaperRetriever
from app.tools.pdf_parser import PDFParser
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


def retrieve_content_node(state: ResearchState) -> Dict[str, Any]:
    """Download full-text PDF where accessible; otherwise gracefully fall back to abstract."""
    raw_selected = state.get("selected_papers", [])
    papers = [Paper.model_validate(p) for p in raw_selected]

    retriever = PaperRetriever()
    contents: List[PaperContent] = []

    for paper in papers:
        pdf_bytes = retriever.retrieve_pdf_bytes(paper)
        content = PDFParser.parse_paper(paper, pdf_bytes=pdf_bytes)
        contents.append(content)

    return {
        "paper_contents": [c.model_dump() for c in contents],
        "status": "content_retrieved",
    }


def extract_evidence_node(state: ResearchState) -> Dict[str, Any]:
    """Extract structured analyses and grounded atomic evidence records from paper content."""
    raw_selected = state.get("selected_papers", [])
    raw_contents = state.get("paper_contents", [])

    papers = [Paper.model_validate(p) for p in raw_selected]
    content_map = {c["paper_id"]: PaperContent.model_validate(c) for c in raw_contents}

    extractor = ExtractorAgent()
    analyses: List[PaperAnalysis] = []
    evidence_records: List[Evidence] = []

    for paper in papers:
        content = content_map.get(paper.paper_id)
        if not content:
            content = PDFParser.parse_paper(paper, pdf_bytes=None)

        analysis, ev_items = extractor.extract(paper, content)
        analyses.append(analysis)
        evidence_records.extend(ev_items)

    return {
        "paper_analyses": [a.model_dump() for a in analyses],
        "extracted_evidence": [e.model_dump() for e in evidence_records],
        "status": "evidence_extracted",
    }


def analyze_literature_node(state: ResearchState) -> Dict[str, Any]:
    """Execute Analyst Agent to generate cross-paper thematic synthesis and comparisons."""
    question = state.get("research_question", "")
    plan_dict = state.get("research_plan", {})
    objective = plan_dict.get("objective", f"Synthesize literature regarding: {question}")

    papers = [Paper.model_validate(p) for p in state.get("selected_papers", [])]
    analyses = [PaperAnalysis.model_validate(a) for a in state.get("paper_analyses", [])]
    evidence_records = [Evidence.model_validate(e) for e in state.get("extracted_evidence", [])]

    analyst = AnalystAgent()
    synthesis = analyst.analyze(
        question=question,
        objective=objective,
        papers=papers,
        analyses=analyses,
        evidence_records=evidence_records,
    )

    return {
        "synthesis": synthesis.model_dump(),
        "status": "analyzed",
    }


def critique_node(state: ResearchState) -> Dict[str, Any]:
    """Execute Critic Agent to evaluate research coverage and identify revision tasks."""
    plan_dict = state.get("research_plan", {})
    plan = ResearchPlan.model_validate(plan_dict) if plan_dict else ResearchPlan(
        research_question=state.get("research_question", ""),
        objective="Assess literature",
        tasks=[],
    )

    papers = [Paper.model_validate(p) for p in state.get("selected_papers", [])]
    evidence_records = [Evidence.model_validate(e) for e in state.get("extracted_evidence", [])]
    raw_synthesis = state.get("synthesis", {})
    synthesis = ResearchSynthesis.model_validate(raw_synthesis) if raw_synthesis else ResearchSynthesis()

    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", get_settings().MAX_REVISION_CYCLES)

    critic = CriticAgent()
    critique = critic.evaluate(
        plan=plan,
        papers=papers,
        evidence_records=evidence_records,
        synthesis=synthesis,
        revision_count=revision_count,
        max_revisions=max_revisions,
    )

    return {
        "critique": critique.model_dump(),
        "status": "critiqued",
    }


def check_critique_decision(state: ResearchState) -> str:
    """Evaluate whether to trigger an automated critic revision loop or proceed to citation verification."""
    critique_dict = state.get("critique", {})
    needs_revision = critique_dict.get("needs_revision", False)
    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", get_settings().MAX_REVISION_CYCLES)
    suggested_queries = critique_dict.get("suggested_revision_tasks", [])

    if needs_revision and revision_count < max_revisions and suggested_queries:
        logger.info(
            f"Critic triggered revision cycle {revision_count + 1}/{max_revisions} with {len(suggested_queries)} queries."
        )
        return "prepare_revision"

    return "verify_citations"


def prepare_revision_node(state: ResearchState) -> Dict[str, Any]:
    """Increment revision counter before dispatching revision search tasks."""
    return {
        "revision_count": state.get("revision_count", 0) + 1,
        "status": "revising",
    }


def dispatch_revision_tasks(state: ResearchState) -> List[Send]:
    """Fan-out revision search tasks to search workers."""
    critique_dict = state.get("critique", {})
    suggested_queries = critique_dict.get("suggested_revision_tasks", [])
    raw_scope = state.get("scope", {})

    send_tasks: List[Send] = []
    for i, q in enumerate(suggested_queries):
        task = ResearchTask(
            task_id=f"rev-{i+1}",
            subquestion=f"Targeted literature search: {q}",
            query=q,
            keywords=q.split(),
            priority=1,
        )
        send_tasks.append(
            Send("search_worker", {"task": task.model_dump(), "scope": raw_scope})
        )
    return send_tasks


def verify_citations_node(state: ResearchState) -> Dict[str, Any]:
    """Verify bibliographic metadata and claim grounding for cited papers."""
    papers = [Paper.model_validate(p) for p in state.get("selected_papers", [])]
    evidence_records = [Evidence.model_validate(e) for e in state.get("extracted_evidence", [])]

    checks = CitationVerifier.verify_all(papers=papers, evidence_records=evidence_records)

    return {
        "verified_citations": [c.model_dump() for c in checks],
        "status": "citations_verified",
    }


def human_review_node(state: ResearchState) -> Dict[str, Any]:
    """Checkpoint interrupt presenting review package to human reviewer before finalization."""
    raw_scope = state.get("scope", {})
    if isinstance(raw_scope, ResearchScope):
        skip_review = raw_scope.skip_human_review
    elif isinstance(raw_scope, dict):
        if "skip_human_review" in raw_scope:
            skip_review = bool(raw_scope["skip_human_review"])
        else:
            try:
                skip_review = ResearchScope.model_validate(raw_scope).skip_human_review
            except Exception:
                skip_review = True
    else:
        skip_review = True

    papers = [Paper.model_validate(p) for p in state.get("selected_papers", [])]
    evidence = [Evidence.model_validate(e) for e in state.get("extracted_evidence", [])]
    critique = state.get("critique", {})
    citation_checks = [CitationCheck.model_validate(c) for c in state.get("verified_citations", [])]

    review_pkg = ReviewPackage(
        research_question=state.get("research_question", ""),
        objective=state.get("research_plan", {}).get("objective", ""),
        selected_papers_count=len(papers),
        papers_summary=[
            {"paper_id": p.paper_id, "title": p.title, "year": p.year, "doi": p.doi}
            for p in papers
        ],
        evidence_count=len(evidence),
        key_evidence=[e.model_dump() for e in evidence[:6]],
        critique_score=critique.get("quality_score", 1.0),
        missing_topics=critique.get("missing_topics", []),
        citation_checks=citation_checks,
        unsupported_claims_count=sum(1 for c in citation_checks if not c.claim_supported),
    )

    if skip_review:
        return {
            "review_package": review_pkg.model_dump(),
            "human_approved": True,
            "human_feedback": None,
            "status": "human_approved",
        }

    # Pause graph execution with checkpoint interrupt!
    decision = interrupt(review_pkg.model_dump())

    # When resumed via Command(resume=...):
    action = "approve"
    feedback = None
    if isinstance(decision, dict):
        action = decision.get("action", "approve")
        feedback = decision.get("feedback")
    elif isinstance(decision, str):
        action = decision

    if action == "approve":
        return {
            "review_package": review_pkg.model_dump(),
            "human_approved": True,
            "human_feedback": feedback,
            "status": "human_approved",
        }
    elif action in ("request_revision", "revise"):
        return {
            "review_package": review_pkg.model_dump(),
            "human_approved": False,
            "human_feedback": feedback,
            "status": "human_revision_requested",
        }
    else:  # reject
        return {
            "review_package": review_pkg.model_dump(),
            "human_approved": False,
            "human_feedback": feedback,
            "status": "rejected",
        }


def check_human_decision(state: ResearchState) -> str:
    """Route according to reviewer decision."""
    status = state.get("status")
    if status == "rejected":
        return "mark_rejected"
    elif status == "human_revision_requested":
        return "prepare_human_revision"
    return "synthesize_summary"


def prepare_human_revision_node(state: ResearchState) -> Dict[str, Any]:
    """Increment revision counter before dispatching human revision tasks."""
    return {
        "revision_count": state.get("revision_count", 0) + 1,
        "status": "revising",
    }


def dispatch_human_revision_tasks(state: ResearchState) -> List[Send]:
    """Fan-out reviewer-instructed revision search tasks."""
    feedback = state.get("human_feedback") or "Address literature gaps and benchmark limitations"
    raw_scope = state.get("scope", {})
    task = ResearchTask(
        task_id=f"human-rev-{uuid.uuid4().hex[:6]}",
        subquestion=f"Reviewer inquiry: {feedback}",
        query=feedback[:100],
        keywords=feedback.split()[:5],
        priority=1,
    )
    return [Send("search_worker", {"task": task.model_dump(), "scope": raw_scope})]


def mark_rejected_node(state: ResearchState) -> Dict[str, Any]:
    """Finalize run as rejected following human review."""
    feedback = state.get("human_feedback") or "Research review package was rejected by reviewer."
    question = state.get("research_question", "")

    return {
        "status": "rejected",
        "final_report": {
            "title": f"Rejected: {question}",
            "research_question": question,
            "content_markdown": f"# Research Run Rejected\n\n**Reviewer Decision:** Rejected\n\n**Feedback:** {feedback}\n\nNo report was finalized.",
            "references": [],
        },
    }


def synthesize_summary_node(state: ResearchState) -> Dict[str, Any]:
    """Synthesize structured literature review report from selected papers, synthesis, and evidence."""
    question = state.get("research_question", "")
    project_id = state.get("project_id", "default-project")
    plan = state.get("research_plan", {})
    papers = [Paper.model_validate(p) for p in state.get("selected_papers", [])]
    evidence_records = [Evidence.model_validate(e) for e in state.get("extracted_evidence", [])]
    synthesis = state.get("synthesis", {})
    verified_citations = [CitationCheck.model_validate(c) for c in state.get("verified_citations", [])]

    from app.agents.writer import ReportWriterAgent
    from app.tools.report_exporter import ReportExporter

    writer = ReportWriterAgent()
    report = writer.write_report(
        research_question=question,
        project_id=project_id,
        papers=papers,
        evidence_records=evidence_records,
        synthesis=synthesis,
        citation_checks=verified_citations,
    )

    report_dict = report.model_dump()
    report_dict["research_question"] = question
    report_dict["objective"] = plan.get("objective", "")
    report_dict["selected_papers_count"] = len(papers)
    report_dict["content_markdown"] = ReportExporter.to_markdown(report)

    return {
        "final_report": report_dict,
        "status": "completed",
    }
