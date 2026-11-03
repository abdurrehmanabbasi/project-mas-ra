"""Unit tests for Pydantic data contract schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.evidence import Critique, Evidence, PaperAnalysis, ResearchSynthesis
from app.schemas.papers import Paper, PaperContent, PaperSource
from app.schemas.report import CitationCheck, ReportSection, ResearchReport
from app.schemas.research import ResearchPlan, ResearchScope, ResearchTask


def test_paper_schema_validation():
    """Verify Paper model validates correct types and generates UUIDs."""
    p = Paper(title="Test Paper", authors=["Alice", "Bob"])
    assert p.paper_id is not None
    assert p.title == "Test Paper"
    assert len(p.authors) == 2
    assert p.sources == []


def test_research_task_and_plan_validation():
    """Verify ResearchPlan validates tasks and constraints."""
    task = ResearchTask(
        subquestion="How does agent routing work?",
        query="agent routing architectures",
    )
    assert task.task_id.startswith("task-")

    plan = ResearchPlan(
        research_question="How does agent routing work?",
        objective="Analyze routing mechanisms",
        tasks=[task],
    )
    assert len(plan.tasks) == 1

    # Should fail if tasks list is empty
    with pytest.raises(ValidationError):
        ResearchPlan(
            research_question="Q?",
            objective="Obj",
            tasks=[],
        )


def test_evidence_and_content_scope():
    """Verify Evidence model requires claim and supporting passage."""
    ev = Evidence(
        paper_id="paper-123",
        claim="Multi-agent architectures achieve higher benchmark accuracy.",
        supporting_passage="The system improved pass@1 by 14% on HumanEval.",
        content_scope="full_text",
    )
    assert ev.evidence_id.startswith("ev-")
    assert ev.content_scope == "full_text"
    assert ev.extraction_confidence == 1.0


def test_citation_check_and_report_schema():
    """Verify CitationCheck and ResearchReport schemas."""
    check = CitationCheck(
        paper_id="p-1",
        doi_valid=True,
        claim_supported=True,
    )
    assert check.citation_id.startswith("cit-")

    report = ResearchReport(
        project_id="proj-1",
        title="Literature Review on Multi-Agent Systems",
        abstract="Executive summary of findings.",
        introduction="Introduction context.",
        comparative_analysis="Comparative table.",
        limitations="Searched up to 2026.",
        sections=[
            ReportSection(title="Architectures", content="Details on architectures."),
        ],
        citation_checks=[check],
    )
    assert report.report_id is not None
    assert len(report.sections) == 1
    assert len(report.citation_checks) == 1

