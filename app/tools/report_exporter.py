"""Export utilities for transforming ResearchReport into Markdown and styled PDF documents."""

import os
from pathlib import Path
from typing import Optional
from app.schemas.report import ResearchReport


class ReportExporter:
    """Exports structured ResearchReport objects to Markdown and PDF files."""

    @staticmethod
    def to_markdown(report: ResearchReport) -> str:
        """Convert a ResearchReport into a standardized, citation-linked Markdown document."""
        lines = [
            f"# {report.title}\n",
            f"**Project ID:** `{report.project_id}`  \n"
            f"**Report ID:** `{report.report_id}`  \n",
            "## Executive Summary",
            report.abstract,
            "",
            report.introduction,
            "",
        ]

        # Thematic Sections
        for section in report.sections:
            lines.append(f"## {section.title}\n")
            lines.append(section.content)
            lines.append("")

        # Key Grounded Evidence
        lines.append("## Key Grounded Evidence\n")
        all_ev_tags = []
        for section in report.sections:
            if section.evidence_ids:
                all_ev_tags.extend(section.evidence_ids)
        if all_ev_tags:
            lines.append(f"Empirical claims in this review are substantiated by evidence records: {', '.join(f'`{eid}`' for eid in set(all_ev_tags))}\n")
        else:
            lines.append("Empirical claims are grounded in extracted literature abstracts and full-text passages.\n")

        # Comparative Analysis
        lines.append(report.comparative_analysis)
        lines.append("")

        # Research Gaps
        lines.append("## Identified Research Gaps & Future Directions\n")
        if report.research_gaps:
            for gap in report.research_gaps:
                lines.append(f"- **{gap}**")
        else:
            lines.append("- No unresolved gaps noted.")
        lines.append("")

        # Limitations
        lines.append("## Threats to Validity & Limitations\n")
        lines.append(report.limitations)
        lines.append("")

        # References
        lines.append(f"## References ({len(report.references)} Publications)\n")
        for ref in report.references:
            cite_label = ref.get("citation_label")
            if not cite_label:
                authors_str = "Unknown Authors"
                raw_authors = ref.get("authors", [])
                if raw_authors:
                    names = [a.get("name") if isinstance(a, dict) else str(a) for a in raw_authors]
                    authors_str = ", ".join(names[:3]) + (" et al." if len(names) > 3 else "")
                year = ref.get("year") or "n.d."
                title = ref.get("title", "Untitled")
                doi_str = f" DOI: {ref.get('doi')}" if ref.get("doi") else ""
                url_str = f" [Link]({ref.get('url')})" if ref.get("url") else ""
                cite_label = f"- [{ref.get('paper_id')}] **{title}**. {authors_str} ({year}).{doi_str}{url_str}"
            else:
                cite_label = f"- {cite_label}"
            lines.append(cite_label)

        # Citation Verification Summary
        if report.citation_checks:
            lines.append("\n## Citation Verification Audit\n")
            valid_dois = sum(1 for c in report.citation_checks if c.doi_valid)
            supported = sum(1 for c in report.citation_checks if c.claim_supported)
            total = len(report.citation_checks)
            lines.append(f"- Verified Citations: **{valid_dois}/{total}** DOIs verified")
            lines.append(f"- Grounded Claims: **{supported}/{total}** claims supported by verbatim evidence records")

        return "\n".join(lines)

    @classmethod
    def export_markdown(cls, report: ResearchReport, output_path: str) -> str:
        """Write report markdown to destination file."""
        content = cls.to_markdown(report)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return output_path

    @classmethod
    def export_pdf(cls, report: ResearchReport, output_path: str) -> str:
        """Render publication-grade PDF using reportlab."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            # Fallback if reportlab missing: write markdown renamed or error
            md_path = output_path.replace(".pdf", ".md")
            cls.export_markdown(report, md_path)
            return md_path

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Title"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=12,
        )
        h1_style = ParagraphStyle(
            "DocH1",
            parent=styles["Heading1"],
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=14,
            spaceAfter=6,
        )
        h2_style = ParagraphStyle(
            "DocH2",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=10,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#2D3748"),
            spaceAfter=6,
        )
        abstract_style = ParagraphStyle(
            "DocAbstract",
            parent=styles["Italic"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4A5568"),
            leftIndent=15,
            rightIndent=15,
            spaceAfter=12,
        )

        story = []

        # Title & Metadata
        story.append(Paragraph(report.title, title_style))
        story.append(Paragraph(f"<b>Project ID:</b> {report.project_id} &nbsp;|&nbsp; <b>Report ID:</b> {report.report_id}", body_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3182CE"), spaceBefore=6, spaceAfter=14))

        # Abstract
        story.append(Paragraph("<b>Executive Abstract</b>", h2_style))
        story.append(Paragraph(report.abstract.replace("\n", "<br/>"), abstract_style))
        story.append(Spacer(1, 8))

        # Introduction
        story.append(Paragraph("1. Introduction", h1_style))
        intro_clean = report.introduction.replace("## Introduction & Problem Context\n\n", "").replace("\n\n", "<br/><br/>")
        story.append(Paragraph(intro_clean, body_style))
        story.append(Spacer(1, 8))

        # Thematic Sections
        sec_num = 2
        for sec in report.sections:
            story.append(Paragraph(f"{sec_num}. {sec.title}", h1_style))
            content_html = sec.content.replace("\n\n", "<br/><br/>").replace("\n", "<br/>")
            story.append(Paragraph(content_html, body_style))
            story.append(Spacer(1, 6))
            sec_num += 1

        # Comparative Analysis
        story.append(Paragraph(f"{sec_num}. Cross-Paper Synthesis & Comparative Analysis", h1_style))
        sec_num += 1
        comp_clean = report.comparative_analysis.replace("## Cross-Paper Comparative Analysis\n", "").replace("\n", "<br/>")
        story.append(Paragraph(comp_clean, body_style))
        story.append(Spacer(1, 8))

        # Research Gaps
        story.append(Paragraph(f"{sec_num}. Open Research Gaps & Future Work", h1_style))
        sec_num += 1
        for gap in report.research_gaps:
            story.append(Paragraph(f"• <b>{gap}</b>", body_style))
        story.append(Spacer(1, 8))

        # Limitations
        story.append(Paragraph(f"{sec_num}. Limitations & Review Validity", h1_style))
        sec_num += 1
        story.append(Paragraph(report.limitations.replace("\n", "<br/>"), body_style))
        story.append(Spacer(1, 10))

        # References
        story.append(PageBreak())
        story.append(Paragraph(f"{sec_num}. References", h1_style))
        for ref in report.references:
            label = ref.get("citation_label") or f"[{ref.get('paper_id')}] {ref.get('title')}"
            doi_info = f" (DOI: {ref.get('doi')})" if ref.get("doi") else ""
            ref_text = f"• {label}{doi_info}"
            story.append(Paragraph(ref_text, body_style))

        doc.build(story)
        return output_path
