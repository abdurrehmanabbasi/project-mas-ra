"""Ablation experiment framework comparing multi-agent architectures against single-agent baselines."""

import json
import os
import time
from typing import Any, Dict, List, Optional

from app.evaluation.metrics import MetricsCalculator, SystemBenchmarkScore
from app.graph.workflow import create_research_graph
from app.schemas.evidence import Evidence
from app.schemas.report import CitationCheck, ResearchReport


class AblationExperimentRunner:
    """Executes controlled ablation experiments comparing full multi-agent against degraded/single-agent configurations."""

    @staticmethod
    def load_benchmarks(benchmark_file: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load benchmark evaluation queries from dataset file."""
        if not benchmark_file or not os.path.exists(benchmark_file):
            default_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "evaluation", "benchmark_queries.json")
            benchmark_file = default_path

        if os.path.exists(benchmark_file):
            with open(benchmark_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    @classmethod
    def run_configuration(
        cls,
        benchmark: Dict[str, Any],
        config_name: str,
        max_revisions: int = 2,
        max_papers: int = 3,
    ) -> Dict[str, Any]:
        """Execute a single experimental configuration on one benchmark query."""
        question = benchmark.get("research_question", "")
        target_topics = benchmark.get("target_topics", [])

        graph = create_research_graph()
        initial_state = {
            "project_id": f"eval-{config_name}",
            "research_question": question,
            "max_revisions": max_revisions,
            "scope": {
                "max_papers": max_papers,
                "preferred_sources": ["arxiv", "semantic_scholar"],
                "skip_human_review": True,
            },
        }

        start_time = time.time()
        thread_id = f"thread-eval-{config_name}-{int(start_time)}"
        final_state = graph.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})
        elapsed = time.time() - start_time

        # Extract Report
        rep_dict = final_state.get("final_report", {})
        report = ResearchReport.model_validate(rep_dict) if rep_dict else ResearchReport(
            project_id=f"eval-{config_name}",
            title="Empty Report",
            abstract="",
            introduction="",
            sections=[],
            comparative_analysis="",
            limitations="",
        )

        evidence_records = [
            Evidence.model_validate(e) for e in final_state.get("extracted_evidence", [])
        ]

        scores = MetricsCalculator.calculate_system_score(
            report=report,
            target_topics=target_topics,
            evidence_records=evidence_records,
            latency_seconds=elapsed,
        )

        return {
            "config_name": config_name,
            "benchmark_id": benchmark.get("benchmark_id"),
            "question": question,
            "latency_seconds": elapsed,
            "scores": scores.to_dict(),
            "papers_reviewed": len(final_state.get("selected_papers", [])),
            "evidence_count": len(evidence_records),
            "revision_count": final_state.get("revision_count", 0),
        }

    @classmethod
    def run_comparative_ablation(cls, benchmark_file: Optional[str] = None) -> Dict[str, Any]:
        """Execute full comparison between multi-agent pipeline and ablated configurations."""
        benchmarks = cls.load_benchmarks(benchmark_file)
        if not benchmarks:
            raise ValueError("No benchmark queries loaded for ablation study.")

        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_benchmarks": len(benchmarks),
            "configurations": {
                "full_multi_agent": [],
                "ablation_no_critic_revisions": [],
            },
            "summary_averages": {},
        }

        for bench in benchmarks:
            # 1. Full Multi-Agent Configuration
            full_res = cls.run_configuration(
                benchmark=bench,
                config_name="full_multi_agent",
                max_revisions=2,
            )
            results["configurations"]["full_multi_agent"].append(full_res)

            # 2. Ablation: No Critic Revision Loop (max_revisions = 0)
            no_critic_res = cls.run_configuration(
                benchmark=bench,
                config_name="ablation_no_critic_revisions",
                max_revisions=0,
            )
            results["configurations"]["ablation_no_critic_revisions"].append(no_critic_res)

        # Compute averages
        for cfg_name, runs in results["configurations"].items():
            avg_composite = sum(r["scores"]["composite_quality_score"] for r in runs) / len(runs)
            avg_claim_support = sum(r["scores"]["citation_metrics"]["claim_support_rate"] for r in runs) / len(runs)
            avg_coverage = sum(r["scores"]["coverage_metrics"]["coverage_score"] for r in runs) / len(runs)
            avg_latency = sum(r["latency_seconds"] for r in runs) / len(runs)

            results["summary_averages"][cfg_name] = {
                "avg_composite_quality_score": round(avg_composite, 4),
                "avg_claim_support_rate": round(avg_claim_support, 4),
                "avg_topic_coverage_score": round(avg_coverage, 4),
                "avg_latency_seconds": round(avg_latency, 2),
            }

        return results

