"""Integration tests for the Ablation Experiment Runner."""

from unittest.mock import patch
import pytest

from app.evaluation.ablation_runner import AblationExperimentRunner
from app.schemas.papers import Paper, PaperSource


def test_load_benchmarks():
    """Verify loading benchmark questions from JSON."""
    benchmarks = AblationExperimentRunner.load_benchmarks()
    assert len(benchmarks) >= 1
    assert "research_question" in benchmarks[0]
    assert "target_topics" in benchmarks[0]


def test_ablation_run_configuration():
    """Verify running a single benchmark through an experimental configuration."""
    benchmark = {
        "benchmark_id": "test-b-1",
        "research_question": "How do multi-agent architectures improve coding benchmarks?",
        "target_topics": ["Multi-agent coordination", "Benchmarking"],
    }

    mock_papers = [
        Paper(
            paper_id="p-mock-1",
            title="AgentBench: Evaluating LLMs as Agents",
            authors=["Xiao Liu", "Hao Yu"],
            year=2023,
            doi="10.48550/arXiv.2308.03688",
            sources=[PaperSource(provider="arxiv", provider_paper_id="2308.03688", url="https://arxiv.org/abs/2308.03688")],
        )
    ]

    with patch("app.tools.arxiv_search.ArxivSearchTool.search", return_value=mock_papers), \
         patch("app.tools.semantic_scholar.SemanticScholarTool.search", return_value=[]), \
         patch("app.tools.paper_retriever.PaperRetriever.retrieve_pdf_bytes", return_value=None):

        result = AblationExperimentRunner.run_configuration(
            benchmark=benchmark,
            config_name="test_multi_agent",
            max_revisions=1,
            max_papers=2,
        )

        assert result["config_name"] == "test_multi_agent"
        assert result["benchmark_id"] == "test-b-1"
        assert "scores" in result
        assert result["scores"]["composite_quality_score"] > 0.0
        assert result["papers_reviewed"] >= 1

