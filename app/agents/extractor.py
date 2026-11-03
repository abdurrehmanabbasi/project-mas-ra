"""Evidence Extraction Agent extracting grounded findings and atomic evidence records."""

import logging
import re
from typing import Any, List, Optional, Tuple
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.config import get_settings
from app.graph.prompts import EXTRACTOR_SYSTEM_PROMPT, EXTRACTOR_USER_TEMPLATE
from app.schemas.evidence import Evidence, PaperAnalysis
from app.schemas.papers import Paper, PaperContent

logger = logging.getLogger(__name__)


class ExtractionPayload(BaseModel):
    """Structured extraction wrapper schema for LLM structured output."""

    methodology: str = Field(description="Summary of approach, models, or algorithms used")
    datasets_used: List[str] = Field(default_factory=list, description="Benchmarks or datasets used")
    findings: List[str] = Field(default_factory=list, description="Key empirical findings")
    limitations: List[str] = Field(default_factory=list, description="Reported threats to validity")
    evidence_items: List[Evidence] = Field(
        default_factory=list, description="Atomic evidence excerpts with verbatim quotes"
    )


class ExtractorAgent:
    """Agent that extracts structured paper analysis and atomic evidence passages from text."""

    def __init__(self, llm: Optional[Any] = None):
        self.settings = get_settings()
        if llm is not None:
            self.llm = llm
        elif self.settings.OPENAI_API_KEY:
            self.llm = ChatOpenAI(
                model=self.settings.OPENAI_MODEL_NAME,
                api_key=self.settings.OPENAI_API_KEY,
                temperature=0.0,
            )
        else:
            self.llm = None

    def extract(self, paper: Paper, content: PaperContent) -> Tuple[PaperAnalysis, List[Evidence]]:
        """Extract methodology, findings, and grounded evidence records from paper content.

        Args:
            paper: Canonical paper metadata.
            content: Retrieved full-text or abstract paper content.

        Returns:
            Tuple of (PaperAnalysis, List[Evidence]).
        """
        # Trim text to fit LLM window if extremely long (max 25,000 chars ~ 6,000 tokens)
        trimmed_text = content.text[:25000] if content.text else ""

        if self.llm is not None and trimmed_text:
            try:
                user_msg = EXTRACTOR_USER_TEMPLATE.format(
                    title=paper.title,
                    authors=", ".join(paper.authors[:4]),
                    year=paper.year or "n.d.",
                    content_scope=content.content_scope,
                    text=trimmed_text,
                )
                structured_llm = self.llm.with_structured_output(ExtractionPayload)
                result: ExtractionPayload = structured_llm.invoke([
                    SystemMessage(content=EXTRACTOR_SYSTEM_PROMPT),
                    HumanMessage(content=user_msg),
                ])

                evidence_list: List[Evidence] = []
                for item in result.evidence_items:
                    # Enforce paper association and provenance scope
                    item.paper_id = paper.paper_id
                    item.content_scope = content.content_scope
                    evidence_list.append(item)

                analysis = PaperAnalysis(
                    paper_id=paper.paper_id,
                    methodology=result.methodology,
                    datasets_used=result.datasets_used,
                    findings=result.findings,
                    limitations=result.limitations,
                    evidence_ids=[e.evidence_id for e in evidence_list],
                )
                return analysis, evidence_list

            except Exception as e:
                logger.error(
                    f"LLM evidence extraction failed for '{paper.title}': {e}. Using heuristic fallback.",
                    exc_info=True,
                )

        # Deterministic heuristic fallback for offline testing or missing LLM key
        return self._heuristic_fallback_extraction(paper, content)

    def _heuristic_fallback_extraction(
        self, paper: Paper, content: PaperContent
    ) -> Tuple[PaperAnalysis, List[Evidence]]:
        """Extract findings and evidence passages using deterministic linguistic patterns."""
        text = content.text or paper.abstract or paper.title
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]

        findings: List[str] = []
        evidence_list: List[Evidence] = []
        datasets: List[str] = []
        limitations: List[str] = []

        # Keywords for pattern matching
        finding_keywords = ["show", "demonstrate", "find", "achieve", "improve", "result", "pass@", "outperform", "evaluate"]
        benchmark_keywords = ["benchmark", "dataset", "humaneval", "mbpp", "swe-bench", "github", "gsm8k"]
        limit_keywords = ["limit", "threat", "future work", "however", "challenge", "bias", "cost"]

        for s in sentences:
            s_lower = s.lower()

            # Datasets
            for bm in benchmark_keywords:
                if bm in s_lower and bm not in [d.lower() for d in datasets]:
                    datasets.append(bm.capitalize())

            # Limitations
            if any(lk in s_lower for lk in limit_keywords):
                if len(limitations) < 3:
                    limitations.append(s)

            # Findings & Evidence
            if any(fk in s_lower for fk in finding_keywords) and len(findings) < 4:
                findings.append(s)
                evidence = Evidence(
                    paper_id=paper.paper_id,
                    evidence_type="finding",
                    claim=s[:180],
                    supporting_passage=s,
                    content_scope=content.content_scope,
                    extraction_confidence=0.85,
                )
                evidence_list.append(evidence)

        # Ensure at least one finding/evidence if text was non-empty
        if not findings and sentences:
            fallback_sentence = sentences[0]
            findings.append(fallback_sentence)
            evidence_list.append(
                Evidence(
                    paper_id=paper.paper_id,
                    evidence_type="finding",
                    claim=fallback_sentence[:180],
                    supporting_passage=fallback_sentence,
                    content_scope=content.content_scope,
                    extraction_confidence=0.75,
                )
            )

        methodology = f"The authors propose and evaluate methods for '{paper.title}'."
        if datasets:
            methodology += f" Evaluated on {', '.join(datasets)}."

        analysis = PaperAnalysis(
            paper_id=paper.paper_id,
            methodology=methodology,
            datasets_used=datasets or ["Custom academic corpus"],
            findings=findings or [f"Explores methodologies for {paper.title}."],
            limitations=limitations or ["Generalizability across diverse real-world systems."],
            evidence_ids=[e.evidence_id for e in evidence_list],
        )

        return analysis, evidence_list
