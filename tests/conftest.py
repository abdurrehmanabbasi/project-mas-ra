"""Pytest fixtures and test environment configuration."""

import pytest
from app.config import Settings
from app.schemas.papers import Paper, PaperSource
from app.schemas.research import ResearchPlan, ResearchScope, ResearchTask


@pytest.fixture
def mock_settings(monkeypatch):
    """Provide isolated settings for testing without relying on host .env."""
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test_db")
    return Settings(
        APP_ENV="testing",
        LOG_LEVEL="DEBUG",
        OPENAI_API_KEY="",
        SEMANTIC_SCHOLAR_API_KEY="",
        DATABASE_URL="postgresql+psycopg://test:test@localhost:5432/test_db",
    )


@pytest.fixture
def sample_arxiv_paper():
    """Sample paper representing an arXiv result."""
    return Paper(
        title="AgentBench: Evaluating LLMs as Agents",
        authors=["Xiao Liu", "Hao Yu", "Hanchen Zhang"],
        year=2023,
        abstract="A benchmark evaluating multi-agent systems and LLMs across diverse environments.",
        doi="10.48550/arXiv.2308.03688",
        sources=[
            PaperSource(
                provider="arxiv",
                provider_paper_id="2308.03688",
                url="https://arxiv.org/abs/2308.03688",
                pdf_url="https://arxiv.org/pdf/2308.03688.pdf",
            )
        ],
        citation_count=120,
    )


@pytest.fixture
def sample_s2_paper():
    """Sample paper representing a Semantic Scholar duplicate result."""
    return Paper(
        title="AgentBench: Evaluating LLMs as Agents.",
        authors=["X. Liu", "H. Yu", "H. Zhang"],
        year=2023,
        abstract="A benchmark evaluating multi-agent systems and LLMs across diverse environments with comprehensive metrics.",
        doi="10.48550/arxiv.2308.03688",
        sources=[
            PaperSource(
                provider="semantic_scholar",
                provider_paper_id="s2-agentbench-id",
                url="https://www.semanticscholar.org/paper/s2-agentbench-id",
                pdf_url="https://arxiv.org/pdf/2308.03688.pdf",
            )
        ],
        citation_count=135,
    )


@pytest.fixture
def sample_research_plan():
    """Sample structured research plan."""
    return ResearchPlan(
        research_question="How are multi-agent AI systems improving autonomous software engineering?",
        objective="Assess multi-agent AI architectures, benchmarks, and limitations in software engineering.",
        tasks=[
            ResearchTask(
                subquestion="What multi-agent architectures are used for software development?",
                query="multi-agent software engineering architecture",
                keywords=["architecture", "multi-agent", "coordination"],
                priority=1,
            ),
            ResearchTask(
                subquestion="What benchmarks are used to evaluate autonomous code generation?",
                query="autonomous software engineering benchmarks evaluation",
                keywords=["benchmark", "SWE-bench", "evaluation"],
                priority=2,
            ),
        ],
        inclusion_criteria=["Published between 2020 and 2026", "Focuses on software engineering"],
        exclusion_criteria=["Unrelated general AI without code application"],
    )

