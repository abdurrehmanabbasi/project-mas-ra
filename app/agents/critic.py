"""Adversarial Critic Agent evaluating literature coverage and triggering targeted revisions."""

import logging
from typing import Any, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.graph.prompts import CRITIC_SYSTEM_PROMPT, CRITIC_USER_TEMPLATE
from app.schemas.evidence import Critique, Evidence, ResearchSynthesis
from app.schemas.papers import Paper
from app.schemas.research import ResearchPlan

logger = logging.getLogger(__name__)


class CriticAgent:
    """Agent that critiques research coverage, detects unsupported claims, and bounds revisions."""

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

    def evaluate(
        self,
        plan: ResearchPlan,
        papers: List[Paper],
        evidence_records: List[Evidence],
        synthesis: ResearchSynthesis,
        revision_count: int = 0,
        max_revisions: Optional[int] = None,
    ) -> Critique:
        """Evaluate literature coverage against the original research plan.

        Args:
            plan: The original structured research plan.
            papers: Currently selected papers.
            evidence_records: Currently extracted evidence records.
            synthesis: The cross-paper synthesis.
            revision_count: Current revision iteration (0-indexed).
            max_revisions: Maximum allowed revision iterations before forced termination.

        Returns:
            A validated Critique schema indicating whether another search iteration is needed.
        """
        max_rev = (
            max_revisions
            if max_revisions is not None
            else self.settings.MAX_REVISION_CYCLES
        )

        # Budget exhaustion guard
        if revision_count >= max_rev:
            logger.info(
                f"Revision budget reached ({revision_count}/{max_rev}). Forcing critique completion without further revisions."
            )
            return Critique(
                quality_score=0.80,
                missing_topics=[],
                unsupported_claims=[],
                needs_revision=False,
                suggested_revision_tasks=[],
            )

        subquestions_str = "\n".join(
            f"- [{t.task_id}] {t.subquestion} (Query: {t.query})" for t in plan.tasks
        )
        papers_summary = "\n".join(
            f"- {p.title} ({p.year or 'n.d.'})" for p in papers[:10]
        )
        synthesis_summary = (
            f"Themes: {len(synthesis.themes)}; "
            f"Comparisons: {len(synthesis.comparisons)}; "
            f"Gaps: {len(synthesis.research_gaps)}"
        )

        if self.llm is not None:
            try:
                user_msg = CRITIC_USER_TEMPLATE.format(
                    objective=plan.objective,
                    subquestions=subquestions_str,
                    paper_count=len(papers),
                    papers_summary=papers_summary,
                    synthesis_summary=synthesis_summary,
                    revision_count=revision_count,
                    max_revisions=max_rev,
                )
                structured_llm = self.llm.with_structured_output(Critique)
                result = structured_llm.invoke([
                    SystemMessage(content=CRITIC_SYSTEM_PROMPT),
                    HumanMessage(content=user_msg),
                ])
                if isinstance(result, Critique):
                    # Guarantee budget limit is respected
                    if revision_count >= max_rev:
                        result.needs_revision = False
                    return result

            except Exception as e:
                logger.error(f"Critic LLM evaluation failed: {e}. Using deterministic critique.", exc_info=True)

        return self._heuristic_fallback_critique(
            plan, papers, evidence_records, synthesis, revision_count, max_rev
        )

    def _heuristic_fallback_critique(
        self,
        plan: ResearchPlan,
        papers: List[Paper],
        evidence_records: List[Evidence],
        synthesis: ResearchSynthesis,
        revision_count: int,
        max_revisions: int,
    ) -> Critique:
        """Deterministic evaluation of topic coverage and revision decisions."""
        missing_topics: List[str] = []
        suggested_tasks: List[str] = []

        all_paper_text = " ".join((p.title + " " + (p.abstract or "")) for p in papers).lower()

        # Check coverage of each task subquestion
        for task in plan.tasks:
            # Check if keywords appear in corpus
            matched = any(kw.lower() in all_paper_text for kw in task.keywords)
            if not matched:
                missing_topics.append(task.subquestion)
                suggested_tasks.append(f"{task.query} state of the art")

        # Evaluate quality score based on paper count and coverage
        coverage_ratio = (
            (len(plan.tasks) - len(missing_topics)) / len(plan.tasks)
            if plan.tasks
            else 1.0
        )
        paper_score = min(1.0, len(papers) / max(3, len(plan.tasks)))
        quality_score = round(0.6 * coverage_ratio + 0.4 * paper_score, 2)

        # Trigger revision only if score is low and budget allows
        needs_revision = (
            quality_score < 0.75
            and revision_count < max_revisions
            and len(suggested_tasks) > 0
        )

        return Critique(
            quality_score=quality_score,
            missing_topics=missing_topics,
            unsupported_claims=[],
            needs_revision=needs_revision,
            suggested_revision_tasks=suggested_tasks[:2],
        )
