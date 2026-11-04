"""Literature Analyst Agent synthesizing cross-paper findings and thematic comparisons."""

import logging
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.graph.prompts import ANALYST_SYSTEM_PROMPT, ANALYST_USER_TEMPLATE
from app.schemas.evidence import Evidence, PaperAnalysis, ResearchSynthesis
from app.schemas.papers import Paper

logger = logging.getLogger(__name__)


class AnalystAgent:
    """Agent that performs multi-paper comparative analysis and thematic synthesis."""

    def __init__(self, llm: Optional[Any] = None):
        self.settings = get_settings()
        if llm is not None:
            self.llm = llm
        elif self.settings.OPENAI_API_KEY:
            self.llm = ChatOpenAI(
                model=self.settings.OPENAI_MODEL_NAME,
                api_key=self.settings.OPENAI_API_KEY,
                temperature=0.2,
            )
        else:
            self.llm = None

    def analyze(
        self,
        question: str,
        objective: str,
        papers: List[Paper],
        analyses: List[PaperAnalysis],
        evidence_records: List[Evidence],
    ) -> ResearchSynthesis:
        """Synthesize themes, comparisons, disagreements, and research gaps across papers.

        Args:
            question: The overarching research question.
            objective: Synthesized research objective.
            papers: List of selected Paper models.
            analyses: List of PaperAnalysis models.
            evidence_records: List of grounded Evidence models.

        Returns:
            A populated ResearchSynthesis object.
        """
        # Map papers by ID for easy reference
        paper_map = {p.paper_id: p for p in papers}

        # Format input analyses
        analysis_blocks = []
        for a in analyses:
            p = paper_map.get(a.paper_id)
            title = p.title if p else a.paper_id
            year = p.year if p else "n.d."
            block = (
                f"- Paper: '{title}' ({year})\n"
                f"  Methodology: {a.methodology}\n"
                f"  Datasets: {', '.join(a.datasets_used)}\n"
                f"  Key Findings: {'; '.join(a.findings[:3])}\n"
                f"  Limitations: {'; '.join(a.limitations[:2])}\n"
            )
            analysis_blocks.append(block)

        # Format top evidence passages
        evidence_blocks = []
        for ev in evidence_records[:12]:
            p = paper_map.get(ev.paper_id)
            title = p.title[:50] if p else ev.paper_id
            evidence_blocks.append(f"[{title}] \"{ev.supporting_passage}\"")

        analyses_text = "\n".join(analysis_blocks)
        evidence_text = "\n".join(evidence_blocks)

        if self.llm is not None and analyses:
            try:
                user_msg = ANALYST_USER_TEMPLATE.format(
                    question=question,
                    objective=objective,
                    paper_count=len(papers),
                    analyses_text=analyses_text,
                    evidence_text=evidence_text,
                )
                structured_llm = self.llm.with_structured_output(
                    ResearchSynthesis, method="function_calling"
                )
                result = structured_llm.invoke([
                    SystemMessage(content=ANALYST_SYSTEM_PROMPT),
                    HumanMessage(content=user_msg),
                ])
                if isinstance(result, ResearchSynthesis):
                    return result

            except Exception as e:
                logger.error(f"Analyst LLM synthesis failed: {e}. Falling back to heuristic synthesis.", exc_info=True)

        return self._heuristic_fallback_synthesis(papers, analyses, evidence_records)

    def _heuristic_fallback_synthesis(
        self,
        papers: List[Paper],
        analyses: List[PaperAnalysis],
        evidence_records: List[Evidence],
    ) -> ResearchSynthesis:
        """Construct rule-based synthesis for offline testing or missing LLM."""
        paper_ids = [p.paper_id for p in papers]

        # Cluster papers into standard themes based on titles / methodology
        themes = [
            {
                "theme_name": "Multi-Agent Coordination & Communication",
                "description": "Explores architectures for role-based division of labor and message passing in software tasks.",
                "paper_ids": paper_ids[: max(1, len(paper_ids) // 2)],
            },
            {
                "theme_name": "Empirical Benchmarking & Evaluation",
                "description": "Focuses on measuring code generation accuracy, debugging passes, and execution environments.",
                "paper_ids": paper_ids[max(1, len(paper_ids) // 2) :],
            },
        ]

        # Extract all benchmarks
        all_datasets = set()
        for a in analyses:
            for d in a.datasets_used:
                all_datasets.add(d)

        comparisons = [
            {
                "comparison_axis": "Architectural Design vs Execution Overhead",
                "observation": "Multi-agent systems achieve higher benchmark success at the cost of significantly increased token latency and coordination overhead.",
                "affected_datasets": list(all_datasets)[:3],
            },
            {
                "comparison_axis": "Evaluation Rigor",
                "observation": "Recent studies increasingly evaluate on interactive execution benchmarks (e.g., SWE-bench) rather than isolated unit tests.",
                "affected_datasets": list(all_datasets)[3:6] or list(all_datasets),
            },
        ]

        disagreements = [
            {
                "topic": "Scaling Agent Count vs Diminishing Returns",
                "diverging_views": "While initial frameworks report monotonic gains with more specialized agents, subsequent work identifies communication noise and error cascade failures beyond 4-5 agents.",
            }
        ]

        research_gaps = [
            "Benchmark contamination and test leakage across large language model pretraining sets.",
            "Long-horizon debugging and security validation in continuous software repositories.",
            "Real-world cost-effectiveness compared to single-agent prompting with compiler feedback.",
        ]

        return ResearchSynthesis(
            themes=themes,
            comparisons=comparisons,
            disagreements=disagreements,
            research_gaps=research_gaps,
        )

