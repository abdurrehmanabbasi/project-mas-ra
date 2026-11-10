"""Unit tests for ReportExporter (Markdown & PDF)."""

import os
import tempfile
from app.schemas.report import CitationCheck, ReportSection, ResearchReport
from app.tools.report_exporter import ReportExporter


def test_export_markdown_and_pdf():
    """Verify that ReportExporter produces valid Markdown and PDF files."""
    report = ResearchReport(
        report_id="test-rep-001",
        project_id="proj-42",
        title="Systematic Literature Review: Autonomous Agent Systems",
        abstract="This is the executive summary abstract of the systematic review.",
        introduction="## Introduction\nAutonomous agents represent a paradigm shift in software engineering.",
        sections=[
            ReportSection(
                title="Thematic Synthesis: Multi-Agent Architectures",
                content="Multi-agent architectures separate planning and execution responsibilities.",
                evidence_ids=["ev-101", "ev-102"],
            )
        ],
        comparative_analysis="Cross-paper synthesis reveals trade-offs between latency and accuracy.",
        research_gaps=["Standardized real-world benchmarks."],
        limitations="Searched arXiv and Semantic Scholar only.",
        references=[
            {
                "paper_id": "p-1",
                "title": "AgentBench: A Benchmark for LLMs as Agents",
                "authors": ["Xiao Liu", "Hao Yu"],
                "year": 2023,
                "doi": "10.48550/arXiv.2308.03688",
                "url": "https://arxiv.org/abs/2308.03688",
                "citation_label": "[p-1] Xiao Liu, Hao Yu (2023). AgentBench: A Benchmark for LLMs as Agents.",
            }
        ],
        citation_checks=[
            CitationCheck(citation_id="cit-1", paper_id="p-1", doi_valid=True, claim_supported=True)
        ],
    )

    # 1. Test markdown string generation
    md_str = ReportExporter.to_markdown(report)
    assert "# Systematic Literature Review: Autonomous Agent Systems" in md_str
    assert "## Executive Summary" in md_str
    assert "## Key Grounded Evidence" in md_str
    assert "## References (1 Publications)" in md_str
    assert "Verified Citations: **1/1**" in md_str

    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = os.path.join(tmpdir, "review.md")
        pdf_path = os.path.join(tmpdir, "review.pdf")

        # 2. Test writing markdown to file
        saved_md = ReportExporter.export_markdown(report, md_path)
        assert os.path.exists(saved_md)
        with open(saved_md, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Autonomous Agent Systems" in content

        # 3. Test writing PDF to file
        saved_pdf = ReportExporter.export_pdf(report, pdf_path)
        assert os.path.exists(saved_pdf)
        assert os.path.getsize(saved_pdf) > 500  # Non-trivial PDF output


def test_export_pdf_escapes_xml_characters(tmp_path):
    """Verify ReportExporter handles raw <, >, & characters and markdown styling in PDF output."""
    report = ResearchReport(
        report_id="rep-xml-test",
        project_id="proj-xml",
        title="Frameworks & Benchmarks: Accuracy < 0.9 & Speed > 1.5x",
        abstract="Evaluates Q&A systems with **bold findings** & `inline_code` where loss < 0.05.",
        introduction="Intro covering A & B < C > D.",
        sections=[
            ReportSection(
                title="Section 1 & 2",
                content="Content with <raw_tag> & **emphasis**.",
            )
        ],
        comparative_analysis="System A > System B & C < D.",
        research_gaps=["Benchmark coverage < 50% & lack of standards"],
        limitations="Limited to < 5 papers & open-access repositories.",
    )
    pdf_path = str(tmp_path / "escaped.pdf")
    saved = ReportExporter.export_pdf(report, pdf_path)
    assert os.path.exists(saved)
    assert os.path.getsize(saved) > 500

