"""Research Planner Agent responsible for decomposing questions into structured search plans."""

import logging
from typing import Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.graph.prompts import PLANNER_SYSTEM_PROMPT, PLANNER_USER_TEMPLATE
from app.schemas.research import ResearchPlan, ResearchScope, ResearchTask

logger = logging.getLogger(__name__)


class PlannerAgent:
    """Agent that creates structured literature review plans from a user inquiry."""

    def __init__(self, llm: Optional[Any] = None):
        self.settings = get_settings()
        if llm is not None:
            self.llm = llm
        elif self.settings.OPENAI_API_KEY:
            self.llm = ChatOpenAI(
                model=self.settings.OPENAI_MODEL_NAME,
                api_key=self.settings.OPENAI_API_KEY,
                temperature=0.1,
            )
        else:
            self.llm = None

    def plan(self, question: str, scope: Optional[ResearchScope] = None) -> ResearchPlan:
        """Generate a structured research plan.

        Args:
            question: The high-level research question.
            scope: Optional constraints such as date range and target paper count.

        Returns:
            A validated ResearchPlan object.
        """
        scope = scope or ResearchScope()
        start_yr = scope.date_range_start or "Any"
        end_yr = scope.date_range_end or "Any"
        sources_str = ", ".join(scope.preferred_sources)

        user_content = PLANNER_USER_TEMPLATE.format(
            research_question=question,
            start_year=start_yr,
            end_year=end_yr,
            max_papers=scope.max_papers,
            preferred_sources=sources_str,
        )

        if self.llm is not None:
            try:
                structured_llm = self.llm.with_structured_output(ResearchPlan)
                result = structured_llm.invoke([
                    SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                    HumanMessage(content=user_content),
                ])
                if isinstance(result, ResearchPlan):
                    return result
            except Exception as e:
                logger.error(f"Planner LLM generation error: {e}. Falling back to rule-based plan.", exc_info=True)

        # Robust heuristic fallback for offline testing or missing LLM key
        return self._heuristic_fallback_plan(question, scope)

    def _heuristic_fallback_plan(self, question: str, scope: ResearchScope) -> ResearchPlan:
        """Create a deterministic fallback plan when LLM is unavailable."""
        words = [w for w in question.replace("?", "").split() if len(w) > 3]
        primary_keywords = words[:4] if words else ["multi-agent", "systems"]

        tasks = [
            ResearchTask(
                subquestion=f"What are the core architectures and models addressing: {question}?",
                query=f"{' '.join(primary_keywords)} architectures",
                keywords=primary_keywords + ["architecture", "framework"],
                priority=1,
            ),
            ResearchTask(
                subquestion="What benchmarks and empirical evaluation methodologies are standard?",
                query=f"{' '.join(primary_keywords[:2])} benchmark evaluation",
                keywords=["benchmark", "evaluation", "empirical"],
                priority=2,
            ),
            ResearchTask(
                subquestion="What are the current limitations, trade-offs, and open research challenges?",
                query=f"{' '.join(primary_keywords[:2])} limitations challenges",
                keywords=["limitations", "challenges", "trade-offs"],
                priority=3,
            ),
        ]

        return ResearchPlan(
            research_question=question,
            objective=f"Investigate academic literature regarding: {question}",
            tasks=tasks,
            inclusion_criteria=[
                f"Published between {scope.date_range_start or 2018} and {scope.date_range_end or 2026}",
                "Focuses on autonomous software engineering or multi-agent systems",
            ],
            exclusion_criteria=[
                "Pure opinion or non-peer-reviewed blog articles",
                "Unrelated domain applications without architectural or evaluation details",
            ],
        )

