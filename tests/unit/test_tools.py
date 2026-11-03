"""Unit tests for arXiv and Semantic Scholar search tools using mocks."""

from unittest.mock import MagicMock, patch
from app.tools.arxiv_search import ArxivSearchTool
from app.tools.semantic_scholar import SemanticScholarTool


def test_arxiv_search_tool_parsing():
    """Verify ArxivSearchTool processes raw results into normalized Paper schemas."""
    mock_entry = MagicMock()
    mock_entry.entry_id = "http://arxiv.org/abs/2308.03688v1"
    mock_entry.title = "AgentBench: Evaluating LLMs as Agents"
    mock_entry.summary = "A benchmark summary line 1\nline 2."
    mock_entry.published.year = 2023
    mock_entry.doi = "10.48550/arXiv.2308.03688"
    mock_entry.pdf_url = "https://arxiv.org/pdf/2308.03688.pdf"

    mock_author = MagicMock()
    mock_author.name = "Xiao Liu"
    mock_entry.authors = [mock_author]

    tool = ArxivSearchTool(request_delay=0.0)
    with patch.object(tool.client, "results", return_value=[mock_entry]):
        papers = tool.search("agentbench", max_results=1)

    assert len(papers) == 1
    p = papers[0]
    assert p.title == "AgentBench: Evaluating LLMs as Agents"
    assert p.year == 2023
    assert p.authors == ["Xiao Liu"]
    assert p.sources[0].provider == "arxiv"
    assert p.sources[0].provider_paper_id == "2308.03688v1"
    assert "\n" not in p.abstract


def test_semantic_scholar_tool_parsing():
    """Verify SemanticScholarTool handles responses and normalizes records."""
    mock_response = {
        "data": [
            {
                "paperId": "s2_abc123",
                "title": "Communicative Agents for Software Development",
                "year": 2023,
                "authors": [{"name": "Chen Qian"}, {"name": "Yujia Wei"}],
                "abstract": "We present ChatDev...",
                "citationCount": 450,
                "externalIds": {"DOI": "10.1145/3611643.3616265"},
                "openAccessPdf": {"url": "https://arxiv.org/pdf/2307.07924.pdf"},
                "url": "https://www.semanticscholar.org/paper/s2_abc123",
            }
        ]
    }

    tool = SemanticScholarTool(timeout_seconds=2)
    normalized = tool._normalize_results(mock_response["data"])

    assert len(normalized) == 1
    p = normalized[0]
    assert p.title == "Communicative Agents for Software Development"
    assert p.authors == ["Chen Qian", "Yujia Wei"]
    assert p.citation_count == 450
    assert p.doi == "10.1145/3611643.3616265"
    assert p.sources[0].provider == "semantic_scholar"
    assert p.sources[0].pdf_url == "https://arxiv.org/pdf/2307.07924.pdf"


def test_semantic_scholar_retry_on_429():
    """Verify SemanticScholarTool retries on status code 429."""
    tool = SemanticScholarTool(timeout_seconds=2)

    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "data": [
            {"paperId": "retried_id", "title": "Paper after 429", "year": 2024}
        ]
    }

    with patch("httpx.Client.get", side_effect=[mock_resp_429, mock_resp_200]):
        with patch("time.sleep"):  # Mock sleep so test runs instantaneously
            papers = tool.search("query", max_results=1)

    assert len(papers) == 1
    assert papers[0].title == "Paper after 429"

