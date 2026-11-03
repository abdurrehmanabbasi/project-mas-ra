"""Unit tests for DatabaseService and SQLAlchemy models."""

import pytest
from app.database.service import DatabaseService


def test_database_project_crud():
    """Verify project creation, retrieval, and listing."""
    project = DatabaseService.create_project(
        title="Test Multi-Agent Project",
        research_question="How do LLM agents collaborate on software engineering tasks?",
        scope={"max_papers": 5, "skip_human_review": True},
    )
    assert project.id is not None
    assert project.title == "Test Multi-Agent Project"
    assert project.status == "active"

    fetched = DatabaseService.get_project(project.id)
    assert fetched is not None
    assert fetched.id == project.id
    assert fetched.research_question == project.research_question

    all_projects = DatabaseService.list_projects()
    assert len(all_projects) >= 1
    assert any(p.id == project.id for p in all_projects)


def test_database_run_and_report_lifecycle():
    """Verify research run lifecycle and report persistence."""
    project = DatabaseService.create_project(
        title="Lifecycle Run Project",
        research_question="Evaluating self-refining agent workflows.",
    )

    run = DatabaseService.create_run(
        project_id=project.id,
        thread_id=f"thread-{project.id}",
        scope_override={"max_papers": 3},
    )
    assert run.id is not None
    assert run.status == "queued"

    # Update run status
    updated_run = DatabaseService.update_run_status(
        run_id=run.id,
        status="completed",
        current_phase="report_synthesized",
        papers_count=3,
        evidence_count=6,
    )
    assert updated_run.status == "completed"
    assert updated_run.papers_count == 3
    assert updated_run.evidence_count == 6

    # Save Report
    report = DatabaseService.save_report(
        project_id=project.id,
        run_id=run.id,
        title="Systematic Review: Agent Self-Refinement",
        report_dict={"title": "Systematic Review: Agent Self-Refinement", "abstract": "Test abstract."},
        markdown_content="# Systematic Review: Agent Self-Refinement\n\nTest content.",
    )
    assert report.id is not None
    assert report.title == "Systematic Review: Agent Self-Refinement"

    fetched_report = DatabaseService.get_report_by_run(run.id)
    assert fetched_report is not None
    assert fetched_report.id == report.id
    assert "Agent Self-Refinement" in fetched_report.markdown_content

