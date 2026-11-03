"""REST API endpoints for research project lifecycle, execution, and report export."""

import asyncio
import json
import logging
import os
import tempfile
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from fastapi.responses import FileResponse, PlainTextResponse
from langgraph.types import Command

from app.database.service import DatabaseService
from app.graph.workflow import create_research_graph
from app.schemas.api import (
    HumanReviewDecision,
    ProjectCreateRequest,
    ProjectResponse,
    RunStartRequest,
    RunStatusResponse,
)
from app.schemas.report import ResearchReport
from app.schemas.research import ResearchScope
from app.tools.report_exporter import ReportExporter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["research"])

# In-memory registry for active running graphs/threads
_ACTIVE_GRAPHS: Dict[str, Any] = {}


def _get_or_create_graph(thread_id: str):
    if thread_id not in _ACTIVE_GRAPHS:
        _ACTIVE_GRAPHS[thread_id] = create_research_graph()
    return _ACTIVE_GRAPHS[thread_id]


async def _execute_graph_run(project_id: str, run_id: str, thread_id: str, initial_state: Dict[str, Any]):
    """Background task executing the LangGraph pipeline."""
    graph = _get_or_create_graph(thread_id)
    config = {"configurable": {"thread_id": thread_id}}

    DatabaseService.update_run_status(run_id=run_id, status="running", current_phase="planning")

    try:
        # Run graph in threadpool so it doesn't block the async event loop
        final_state = await asyncio.to_thread(graph.invoke, initial_state, config=config)

        # Check if paused at interrupt
        state_snapshot = graph.get_state(config)
        if state_snapshot.next:
            # Graph is paused at an interrupt (e.g. human_review)
            selected = final_state.get("selected_papers", []) if final_state else []
            evidence = final_state.get("extracted_evidence", []) if final_state else []
            DatabaseService.update_run_status(
                run_id=run_id,
                status="waiting_for_review",
                current_phase="human_review",
                papers_count=len(selected),
                evidence_count=len(evidence),
            )
            return

        # Completed normally
        status = final_state.get("status", "completed")
        if status == "rejected":
            DatabaseService.update_run_status(
                run_id=run_id,
                status="rejected",
                current_phase="rejected_by_reviewer",
            )
            return

        final_report = final_state.get("final_report")
        if final_report:
            title = final_report.get("title", f"Literature Review: {initial_state.get('research_question')}")
            md_content = final_report.get("content_markdown", "")
            DatabaseService.save_report(
                project_id=project_id,
                run_id=run_id,
                title=title,
                report_dict=final_report,
                markdown_content=md_content,
            )

        selected = final_state.get("selected_papers", [])
        evidence = final_state.get("extracted_evidence", [])
        DatabaseService.update_run_status(
            run_id=run_id,
            status="completed",
            current_phase="report_synthesized",
            papers_count=len(selected),
            evidence_count=len(evidence),
        )

    except Exception as e:
        logger.error(f"Error executing run {run_id}: {e}", exc_info=True)
        DatabaseService.update_run_status(
            run_id=run_id,
            status="failed",
            current_phase="error",
            error_message=str(e),
        )


# ---------------------------------------------------------------------------
# Project Endpoints
# ---------------------------------------------------------------------------

@router.post("/projects", response_model=ProjectResponse)
def create_project(request: ProjectCreateRequest):
    """Create a new research project."""
    scope_dict = request.scope.model_dump() if request.scope else {}
    project = DatabaseService.create_project(
        title=request.title,
        research_question=request.research_question,
        scope=scope_dict,
    )
    return ProjectResponse(
        project_id=project.id,
        title=project.title,
        research_question=project.research_question,
        status=project.status,
        created_at=project.created_at.isoformat(),
    )


@router.get("/projects", response_model=List[ProjectResponse])
def list_projects():
    """List all research projects."""
    projects = DatabaseService.list_projects()
    return [
        ProjectResponse(
            project_id=p.id,
            title=p.title,
            research_question=p.research_question,
            status=p.status,
            created_at=p.created_at.isoformat(),
        )
        for p in projects
    ]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str):
    """Retrieve details for a single research project."""
    project = DatabaseService.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        project_id=project.id,
        title=project.title,
        research_question=project.research_question,
        status=project.status,
        created_at=project.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Run Endpoints
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/runs", response_model=RunStatusResponse)
def start_run(project_id: str, request: RunStartRequest, background_tasks: BackgroundTasks):
    """Launch an autonomous multi-agent research run."""
    project = DatabaseService.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    thread_id = f"thread-{uuid.uuid4().hex[:12]}"
    scope = request.scope_override.model_dump() if request.scope_override else json.loads(project.scope_json or "{}")

    run = DatabaseService.create_run(
        project_id=project_id,
        thread_id=thread_id,
        scope_override=scope,
    )

    initial_state = {
        "project_id": project_id,
        "research_question": project.research_question,
        "scope": scope,
    }

    # Dispatch to background task
    background_tasks.add_task(_execute_graph_run, project_id, run.id, thread_id, initial_state)

    return RunStatusResponse(
        run_id=run.id,
        project_id=run.project_id,
        status=run.status,
        current_phase=run.current_phase,
        papers_found=run.papers_count,
        evidence_count=run.evidence_count,
    )


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
def get_run_status(run_id: str):
    """Check the real-time execution status of a research run."""
    run = DatabaseService.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunStatusResponse(
        run_id=run.id,
        project_id=run.project_id,
        status=run.status,
        current_phase=run.current_phase,
        papers_found=run.papers_count,
        evidence_count=run.evidence_count,
        error_message=run.error_message,
    )


@router.get("/runs/{run_id}/review")
def get_run_review_package(run_id: str):
    """Retrieve the review package when a run is paused at human-in-the-loop review."""
    run = DatabaseService.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    graph = _get_or_create_graph(run.thread_id)
    config = {"configurable": {"thread_id": run.thread_id}}
    state_snapshot = graph.get_state(config)

    # Check for active interrupt payload
    for task in state_snapshot.tasks:
        if task.interrupts:
            for intr in task.interrupts:
                return intr.value

    # If state has review_package in values
    if "review_package" in state_snapshot.values:
        return state_snapshot.values["review_package"]

    raise HTTPException(status_code=400, detail="Run is not waiting for human review")


@router.post("/runs/{run_id}/review", response_model=RunStatusResponse)
async def submit_human_review(run_id: str, decision: HumanReviewDecision):
    """Submit approval, revision request, or rejection to resume graph execution."""
    run = DatabaseService.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    graph = _get_or_create_graph(run.thread_id)
    config = {"configurable": {"thread_id": run.thread_id}}

    # Resume graph execution with human command
    resume_payload = {"action": decision.action, "feedback": decision.feedback}
    cmd = Command(resume=resume_payload)

    DatabaseService.update_run_status(run_id=run_id, status="running", current_phase=f"human_decision_{decision.action}")

    try:
        final_state = await asyncio.to_thread(graph.invoke, cmd, config=config)

        # Check if paused again at interrupt
        snapshot = graph.get_state(config)
        if snapshot.next:
            DatabaseService.update_run_status(
                run_id=run_id,
                status="waiting_for_review",
                current_phase="human_review",
            )
            return get_run_status(run_id)

        status = final_state.get("status", "completed")
        if status == "rejected":
            DatabaseService.update_run_status(run_id=run_id, status="rejected", current_phase="rejected_by_reviewer")
        else:
            final_report = final_state.get("final_report")
            if final_report:
                title = final_report.get("title", f"Literature Review: {run.project_id}")
                md_content = final_report.get("content_markdown", "")
                DatabaseService.save_report(
                    project_id=run.project_id,
                    run_id=run.id,
                    title=title,
                    report_dict=final_report,
                    markdown_content=md_content,
                )
            selected = final_state.get("selected_papers", [])
            evidence = final_state.get("extracted_evidence", [])
            DatabaseService.update_run_status(
                run_id=run_id,
                status="completed",
                current_phase="report_synthesized",
                papers_count=len(selected),
                evidence_count=len(evidence),
            )

    except Exception as e:
        logger.error(f"Error resuming run {run_id}: {e}", exc_info=True)
        DatabaseService.update_run_status(run_id=run_id, status="failed", error_message=str(e))

    return get_run_status(run_id)


# ---------------------------------------------------------------------------
# Report & Export Endpoints
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/papers")
def get_run_papers(run_id: str):
    """Retrieve discovered and selected papers for a research run."""
    run = DatabaseService.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    graph = _get_or_create_graph(run.thread_id)
    config = {"configurable": {"thread_id": run.thread_id}}
    snapshot = graph.get_state(config)
    selected = snapshot.values.get("selected_papers") or snapshot.values.get("search_results") or []
    if not selected:
        report_model = DatabaseService.get_report_by_run(run_id)
        if report_model:
            rep_data = json.loads(report_model.report_json)
            return rep_data.get("references", [])
    return selected


@router.get("/runs/{run_id}/evidence")
def get_run_evidence(run_id: str):
    """Retrieve all grounded evidence records extracted for a research run."""
    run = DatabaseService.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    graph = _get_or_create_graph(run.thread_id)
    config = {"configurable": {"thread_id": run.thread_id}}
    snapshot = graph.get_state(config)
    return snapshot.values.get("extracted_evidence", [])


@router.get("/runs/{run_id}/report")
def get_run_report(run_id: str):
    """Fetch the synthesized research report JSON."""
    report = DatabaseService.get_report_by_run(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not generated for this run yet")
    return json.loads(report.report_json)


@router.get("/runs/{run_id}/export/markdown")
def export_report_markdown(run_id: str):
    """Download the synthesized literature review in Markdown format."""
    report = DatabaseService.get_report_by_run(run_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not generated for this run yet")

    response = Response(content=report.markdown_content, media_type="text/markdown")
    response.headers["Content-Disposition"] = f'attachment; filename="report_{run_id[:8]}.md"'
    return response


@router.get("/runs/{run_id}/export/pdf")
def export_report_pdf(run_id: str):
    """Download the synthesized literature review in styled PDF format."""
    report_model = DatabaseService.get_report_by_run(run_id)
    if not report_model:
        raise HTTPException(status_code=404, detail="Report not generated for this run yet")

    report_dict = json.loads(report_model.report_json)
    report_obj = ResearchReport.model_validate(report_dict)

    tmp_pdf = os.path.join(tempfile.gettempdir(), f"report_{run_id[:8]}.pdf")
    ReportExporter.export_pdf(report_obj, tmp_pdf)

    return FileResponse(
        path=tmp_pdf,
        filename=f"literature_review_{run_id[:8]}.pdf",
        media_type="application/pdf",
    )

