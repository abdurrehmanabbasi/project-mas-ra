"""CLI runner for executing evaluation benchmarks and printing comparative ablation matrices."""

import argparse
import json
import os
import sys
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.evaluation.ablation_runner import AblationExperimentRunner
from app.schemas.papers import Paper, PaperSource


def mock_sample_corpus():
    """Deterministic mock papers for reproducible offline evaluation."""
    return [
        Paper(
            paper_id="paper-eval-1",
            title="AgentBench: Evaluating LLMs as Agents",
            authors=["Xiao Liu", "Hao Yu"],
            year=2023,
            doi="10.48550/arXiv.2308.03688",
            sources=[PaperSource(provider="arxiv", provider_paper_id="2308.03688", url="https://arxiv.org/abs/2308.03688")],
        ),
        Paper(
            paper_id="paper-eval-2",
            title="SWE-bench: Can Language Models Resolve Real-World GitHub Issues?",
            authors=["Carlos E. Jimenez", "John Yang"],
            year=2024,
            doi="10.48550/arXiv.2310.06770",
            sources=[PaperSource(provider="semantic_scholar", provider_paper_id="swe-bench", url="https://semanticscholar.org/paper/swe")],
        ),
    ]


def main():
    parser = argparse.ArgumentParser(description="Run Milestone 5 evaluation benchmark experiments.")
    parser.add_argument("--benchmarks", type=str, default=None, help="Path to benchmark JSON file")
    parser.add_argument("--output", type=str, default="data/evaluation/ablation_results.json", help="Path to save results JSON")
    args = parser.parse_args()

    print("\n=======================================================")
    print("[EVAL] RUNNING MILESTONE 5 RESEARCH EVALUATION EXPERIMENTS")
    print("=======================================================\n")

    papers = mock_sample_corpus()

    with patch("app.tools.arxiv_search.ArxivSearchTool.search", return_value=papers), \
         patch("app.tools.semantic_scholar.SemanticScholarTool.search", return_value=[]), \
         patch("app.tools.paper_retriever.PaperRetriever.retrieve_pdf_bytes", return_value=None):

        results = AblationExperimentRunner.run_comparative_ablation(args.benchmarks)

    # Save to disk
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("[OK] Benchmark evaluation complete!")
    print(f"Results saved to: {args.output}\n")

    print("[REPORT] COMPARATIVE ABLATION SUMMARY")
    print("---------------------------------------------------------------------------------------------------")
    print(f"{'Configuration':<32} | {'Quality Score':<14} | {'Claim Support':<14} | {'Topic Coverage':<14} | {'Latency':<10}")
    print("---------------------------------------------------------------------------------------------------")
    for cfg, stats in results["summary_averages"].items():
        print(
            f"{cfg:<32} | "
            f"{stats['avg_composite_quality_score']:<14.2f} | "
            f"{stats['avg_claim_support_rate']*100:<13.1f}% | "
            f"{stats['avg_topic_coverage_score']*100:<13.1f}% | "
            f"{stats['avg_latency_seconds']:<9.2f}s"
        )
    print("---------------------------------------------------------------------------------------------------\n")


if __name__ == "__main__":
    main()
