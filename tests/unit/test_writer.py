"""Unit tests for Academic Report Writer Agent."""

import pytest
from app.agents.writer import ReportWriterAgent
from app.schemas.evidence import Evidence
from app.schemas.papers import Paper, PaperSource
from app.schemas.report import CitationCheck, ResearchReport


def test_writer_deterministic_generation():
    """Verify that ReportWriterAgent generates a complete structured report deterministically."""
    writer = ReportWriterAgent()

    papers = [
        Paper(
            paper_id="paper-101",
            title="Evaluating Multi-Agent Systems in Software Engineering",
            authors=["Alice Smith", "Bob Jones"],
            year=2024,
            doi="10.1145/3639478.3640000",
            sources=[PaperSource(provider="arxiv", provider_paper_id="2401.12345", url="https://arxiv.org/abs/2401.12345")],
        ),
        Paper(
            paper_id="paper-102",
            title="Benchmark Leakage in Autonomous Coding Agents",
            authors=["Charlie Brown"],
            year=2023,
            doi="10.1109/ICSE.2023.001",
            sources=[PaperSource(provider="semantic_scholar", provider_paper_id="s2-charlie", url="https://semanticscholar.org/paper/s2")],
        ),
    ]

    evidence_records = [
        Evidence(
            evidence_id="ev-1",
            paper_id="paper-101",
            claim="Multi-agent systems improve bug fix resolution rate by 24% over single-agent baselines.",
            supporting_passage="In our empirical evaluation across 300 Github issues, the multi-agent setup resolved 24% more bugs.",
            content_scope="full_text",
        ),
        Evidence(
            evidence_id="ev-2",
            paper_id="paper-102",
            claim="43% of popular benchmark tasks appear in web pre-training data.",
            supporting_passage="Decontamination audits indicate 43% overlap with pre-2023 public repositories.",
            content_scope="abstract_only",
        ),
    ]

    synthesis = {
        "themes": [
            {
                "theme_name": "Multi-Agent Coordination Paradigms",
                "description": "Architectural divisions between planner, coder, and test executor.",
                "paper_ids": ["paper-101"],
            },
            {
                "theme_name": "Benchmark Contamination & Decontamination",
                "description": "Risks of data memorization in automated code evaluations.",
                "paper_ids": ["paper-102"],
            },
        ],
        "comparisons": [
            {
                "comparison_axis": "Resolution Rate vs Contamination Risk",
                "observation": "Higher accuracy correlated with overlap on standard benchmark tests.",
            }
        ],
        "research_gaps": [
            "Lack of clean, contaminated-free continuous evaluation streams.",
        ],
    }

    citation_checks = [
        CitationCheck(citation_id="c-1", paper_id="paper-101", doi_valid=True, claim_supported=True),
        CitationCheck(citation_id="c-2", paper_id="paper-102", doi_valid=True, claim_supported=True),
    ]

    report = writer.write_report(
        research_question="How effective are multi-agent architectures for software engineering?",
        project_id="proj-test-1",
        papers=papers,
        evidence_records=evidence_records,
        synthesis=synthesis,
        citation_checks=citation_checks,
    )

    assert isinstance(report, ResearchReport)
    assert report.project_id == "proj-test-1"
    assert "Systematic Literature Review" in report.title
    assert len(report.sections) >= 2
    assert len(report.references) == 2
    assert report.references[0]["paper_id"] == "paper-101"
    assert "Alice Smith" in report.references[0]["citation_label"]
    assert len(report.research_gaps) >= 1
    assert len(report.citation_checks) == 2
