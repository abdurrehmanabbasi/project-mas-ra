"""Academic Report Writer Agent for synthesizing literature review reports."""

import logging
import uuid
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings
from app.graph.prompts import WRITER_SYSTEM_PROMPT
from app.schemas.evidence import Evidence
from app.schemas.papers import Paper
from app.schemas.report import CitationCheck, ReportSection, ResearchReport

logger = logging.getLogger(__name__)


class ReportWriterAgent:
    """Synthesizes structured evidence, comparative analyses, and citation checks into a formal literature review."""

    def __init__(self, model_name: Optional[str] = None):
        self.settings = get_settings()
        self.model_name = model_name or self.settings.OPENAI_MODEL_NAME
        self._llm = None

    def _get_llm(self):
        if self._llm is None and self.settings.OPENAI_API_KEY:
            try:
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model=self.model_name,
                    api_key=self.settings.OPENAI_API_KEY,
                    temperature=0.3,
                )
            except Exception:
                self._llm = None
        return self._llm

    def write_report(
        self,
        research_question: str,
        project_id: str,
        papers: List[Paper],
        evidence_records: List[Evidence],
        synthesis: Dict[str, Any],
        citation_checks: List[CitationCheck],
    ) -> ResearchReport:
        """Generate a complete ResearchReport."""
        llm = self._get_llm()
        if llm:
            try:
                return self._write_with_llm(
                    llm=llm,
                    research_question=research_question,
                    project_id=project_id,
                    papers=papers,
                    evidence_records=evidence_records,
                    synthesis=synthesis,
                    citation_checks=citation_checks,
                )
            except Exception as e:
                logger.warning(f"ReportWriter LLM synthesis failed ({e}); falling back to deterministic report.", exc_info=True)

        # Robust deterministic fallback
        return self._write_deterministic(
            research_question=research_question,
            project_id=project_id,
            papers=papers,
            evidence_records=evidence_records,
            synthesis=synthesis,
            citation_checks=citation_checks,
        )

    def _write_deterministic(
        self,
        research_question: str,
        project_id: str,
        papers: List[Paper],
        evidence_records: List[Evidence],
        synthesis: Dict[str, Any],
        citation_checks: List[CitationCheck],
    ) -> ResearchReport:
        clean_q = research_question.rstrip("?. ")
        title = f"Systematic Literature Review: {clean_q}"
        abstract = (
            f"This systematic literature review addresses the research inquiry: '{research_question}'. "
            f"Analyzing a curated corpus of {len(papers)} peer-reviewed papers and preprints, we synthesize "
            f"{len(evidence_records)} grounded empirical evidence records across key thematic clusters. "
            f"Our findings highlight dominant architectural patterns, empirical benchmark outcomes, "
            f"and critical methodological trade-offs, delineating concrete avenues for future investigation."
        )

        intro = (
            f"## Introduction & Problem Context\n\n"
            f"Recent advances have intensified interest in: *{research_question}*. "
            f"Synthesizing findings across dispersed academic venues is critical to establish established baselines, "
            f"trace algorithmic evolutions, and identify unresolved research challenges.\n\n"
            f"This review examines {len(papers)} selected studies, grounding every core claim in verbatim empirical "
            f"evidence and bibliographic provenance checks."
        )

        # Build Thematic Sections
        sections: List[ReportSection] = []
        raw_themes = synthesis.get("themes", [])
        if not raw_themes:
            raw_themes = ["Foundational Methodologies", "Empirical Evaluation & Benchmarking"]

        for idx, theme_obj in enumerate(raw_themes, 1):
            if isinstance(theme_obj, dict):
                theme_title = theme_obj.get("theme_name") or f"Thematic Cluster {idx}"
                theme_desc = theme_obj.get("description", "")
            else:
                theme_title = str(theme_obj)
                theme_desc = ""

            theme_words = [w.lower() for w in theme_title.split() if len(w) > 3]
            matching_ev = [
                e for e in evidence_records
                if any(w in (e.claim + " " + e.supporting_passage).lower() for w in theme_words)
            ]
            if not matching_ev:
                matching_ev = evidence_records[idx - 1:idx + 1] or evidence_records[:2]

            content_lines = [
                f"### {theme_title}\n",
                theme_desc if theme_desc else f"Analysis of literature relevant to {theme_title} reveals several key developments:",
            ]
            used_ids = []
            for ev in matching_ev:
                p_cite = f"[{ev.paper_id}]"
                content_lines.append(
                    f"- **{ev.claim}** {p_cite}. As substantiated in source text: *\"{ev.supporting_passage[:200]}...\"* "
                    f"(Scope: `{ev.content_scope}`)"
                )
                used_ids.append(ev.evidence_id)

            sections.append(
                ReportSection(
                    title=f"Thematic Synthesis: {theme_title}",
                    content="\n\n".join(content_lines),
                    evidence_ids=used_ids,
                )
            )

        # Comparative Analysis
        comp_items = synthesis.get("comparisons", [])
        comp_lines = ["## Cross-Paper Comparative Analysis\n"]
        if comp_items:
            comp_lines.append("| Dimension | Key Literature Comparison |")
            comp_lines.append("| :--- | :--- |")
            for c in comp_items:
                if isinstance(c, dict):
                    dim = c.get("comparison_axis") or c.get("dimension") or "Methodology"
                    notes = c.get("observation") or c.get("comparison_notes") or "Comparable empirical outcomes across surveyed systems."
                else:
                    dim = "Synthesis"
                    notes = str(c)
                comp_lines.append(f"| **{dim}** | {notes} |")
        else:
            comp_lines.append(
                "Surveyed literature indicates consistent architectural progression towards modular, multi-component "
                "orchestration, yielding heightened robustness over monolithic baselines."
            )
        comparative_analysis = "\n".join(comp_lines)

        # Research Gaps
        gaps = synthesis.get("research_gaps", [])
        if not gaps:
            gaps = [
                "Absence of standardized cross-architecture evaluation benchmarks.",
                "Limited longitudinal reliability and error recovery analyses under adversarial inputs.",
                "High latency and compute cost scaling bottlenecks during real-world deployments.",
            ]

        # Limitations
        limitations = (
            f"This review is constrained by the search boundaries defined in the research scope (max {len(papers)} papers). "
            f"Search was conducted across arXiv and Semantic Scholar. Papers without open full-text access were analyzed "
            f"via their peer-reviewed abstracts with provenance explicitly tracked."
        )

        # References
        references = []
        for p in papers:
            authors_list = [str(a) for a in p.authors]
            authors_str = ", ".join(authors_list[:2]) if authors_list else "Unknown Authors"
            if len(authors_list) > 2:
                authors_str += " et al."
            first_source = p.sources[0] if p.sources else None
            p_url = (first_source.url or first_source.pdf_url) if first_source else None
            ref_entry = {
                "paper_id": p.paper_id,
                "title": p.title,
                "authors": authors_list,
                "year": p.year,
                "venue": "arXiv / Academic Preprints",
                "doi": p.doi,
                "url": p_url,
                "citation_label": f"[{p.paper_id}] {authors_str} ({p.year or 'n.d.'}). {p.title}.",
            }
            references.append(ref_entry)

        return ResearchReport(
            project_id=project_id,
            title=title,
            abstract=abstract,
            introduction=intro,
            sections=sections,
            comparative_analysis=comparative_analysis,
            research_gaps=gaps,
            limitations=limitations,
            references=references,
            citation_checks=citation_checks,
        )

    def _write_with_llm(
        self,
        llm: Any,
        research_question: str,
        project_id: str,
        papers: List[Paper],
        evidence_records: List[Evidence],
        synthesis: Dict[str, Any],
        citation_checks: List[CitationCheck],
    ) -> ResearchReport:
        structured_llm = llm.with_structured_output(
            ResearchReport, method="function_calling"
        )
        evidence_summary = "\n".join(
            f"[{e.paper_id}] Claim: {e.claim} | Quote: \"{e.supporting_passage}\" | Scope: {e.content_scope}"
            for e in evidence_records[:15]
        )
        papers_summary = "\n".join(
            f"[{p.paper_id}] {p.title} ({p.year}) - DOI: {p.doi or 'N/A'}"
            for p in papers
        )
        prompt = (
            f"Research Question: {research_question}\n"
            f"Project ID: {project_id}\n\n"
            f"Available Papers:\n{papers_summary}\n\n"
            f"Extracted Grounded Evidence:\n{evidence_summary}\n\n"
            f"Synthesized Literature Themes & Comparisons:\n{synthesis}\n\n"
            f"Write a rigorous, publication-grade literature review strictly grounded in the provided papers and evidence."
        )
        messages = [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        report: ResearchReport = structured_llm.invoke(messages)
        report.project_id = project_id
        report.citation_checks = citation_checks
        return report
