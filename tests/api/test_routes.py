"""Unit and integration tests for FastAPI endpoints."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi import BackgroundTasks

from app.api.routes import (
    create_project,
    export_report_markdown,
    export_report_pdf,
    get_project,
    get_run_report,
    get_run_status,
    list_projects,
    start_run,
    submit_human_review,
)
from app.database.service import DatabaseService
from app.schemas.api import (
    HumanReviewDecision,
    ProjectCreateRequest,
    RunStartRequest,
)
from app.schemas.research import ResearchScope


def test_project_endpoints():
    """Verify project creation, retrieval, and listing."""
    req = ProjectCreateRequest(
        title="Direct Endpoint Study",
        research_question="How do autonomous agents coordinate benchmarks?",
        scope=ResearchScope(max_papers=3, skip_human_review=True),
    )
    project_res = create_project(req)
    assert project_res.project_id is not None
    assert project_res.title == "Direct Endpoint Study"

    # Get project
    fetched = get_project(project_res.project_id)
    assert fetched.project_id == project_res.project_id
    assert fetched.title == project_res.title

    # List projects
    all_p = list_projects()
    assert len(all_p) >= 1
    assert any(p.project_id == project_res.project_id for p in all_p)


def test_start_run_and_status():
    """Verify run creation and status checking."""
    project = DatabaseService.create_project(
        title="Run Creation Project",
        research_question="Evaluating empirical agent performance.",
    )
    bg_tasks = BackgroundTasks()

    run_status = start_run(
        project_id=project.id,
        request=RunStartRequest(),
        background_tasks=bg_tasks,
    )
    assert run_status.run_id is not None
    assert run_status.project_id == project.id
    assert run_status.status == "queued"

    # Check status endpoint
    polled = get_run_status(run_status.run_id)
    assert polled.run_id == run_status.run_id
    assert polled.project_id == project.id


def test_report_and_export_endpoints():
    """Verify report retrieval and export downloads."""
    project = DatabaseService.create_project(
        title="Report Export Project",
        research_question="Synthesizing multi-agent research directions.",
    )
    run = DatabaseService.create_run(project_id=project.id, thread_id=f"thread-{project.id}")

    report_data = {
        "report_id": "rep-test-99",
        "project_id": project.id,
        "title": "Systematic Review: Autonomous Agent Systems",
        "abstract": "Executive summary of the agent review.",
        "introduction": "Introduction context.",
        "sections": [
            {
                "title": "Thematic Synthesis",
                "content": "Synthesized literature content.",
                "evidence_ids": ["ev-1"],
            }
        ],
        "comparative_analysis": "Comparative analysis table.",
        "research_gaps": ["Contamination"],
        "limitations": "Paper boundaries.",
        "references": [
            {
                "paper_id": "p-1",
                "title": "AgentBench",
                "authors": ["Xiao Liu"],
                "year": 2023,
                "citation_label": "[p-1] Xiao Liu (2023). AgentBench.",
            }
        ],
        "citation_checks": [],
    }

    DatabaseService.save_report(
        project_id=project.id,
        run_id=run.id,
        title="Systematic Review: Autonomous Agent Systems",
        report_dict=report_data,
        markdown_content="# Systematic Review: Autonomous Agent Systems\n\nContent...",
    )

    # 1. Test get report JSON
    rep_res = get_run_report(run.id)
    assert rep_res["title"] == "Systematic Review: Autonomous Agent Systems"

    # 2. Test export markdown
    md_res = export_report_markdown(run.id)
    assert md_res.media_type == "text/markdown"
    assert "Systematic Review" in md_res.body.decode("utf-8")

    # 3. Test export PDF
    pdf_res = export_report_pdf(run.id)
    assert pdf_res.media_type == "application/pdf"
