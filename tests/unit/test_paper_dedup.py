"""Unit tests for paper deduplication and source merging."""

from app.schemas.papers import Paper, PaperSource
from app.tools.paper_dedup import PaperDeduplicator


def test_normalize_doi():
    """Verify DOI normalization handles prefixes and case differences."""
    assert (
        PaperDeduplicator.normalize_doi("https://doi.org/10.1145/12345")
        == "10.1145/12345"
    )
    assert (
        PaperDeduplicator.normalize_doi("http://dx.doi.org/10.1145/12345")
        == "10.1145/12345"
    )
    assert PaperDeduplicator.normalize_doi("doi:10.1145/12345") == "10.1145/12345"
    assert (
        PaperDeduplicator.normalize_doi("  10.1145/ABCDE  ") == "10.1145/abcde"
    )
    assert PaperDeduplicator.normalize_doi(None) is None


def test_normalize_title():
    """Verify title normalization ignores punctuation, casing, and spacing."""
    t1 = "MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework"
    t2 = "metagpt meta programming for a multi agent collaborative framework"
    assert PaperDeduplicator.normalize_title(t1) == PaperDeduplicator.normalize_title(t2)


def test_are_duplicates_by_doi(sample_arxiv_paper, sample_s2_paper):
    """Verify duplicate detection when matching normalized DOI is present."""
    assert PaperDeduplicator.are_duplicates(sample_arxiv_paper, sample_s2_paper) is True


def test_are_duplicates_by_title_and_year():
    """Verify duplicate detection by normalized title and matching year."""
    p1 = Paper(
        title="ChatDev: Communicative Agents for Software Development",
        authors=["Chen Qian"],
        year=2023,
    )
    p2 = Paper(
        title="ChatDev: Communicative Agents for Software Development.",
        authors=["C. Qian"],
        year=2024,  # +-1 year tolerance
    )
    assert PaperDeduplicator.are_duplicates(p1, p2) is True


def test_distinct_papers_not_duplicates():
    """Verify distinct papers are not erroneously merged."""
    p1 = Paper(title="SWE-bench: Can Language Models Resolve Real GitHub Issues?", year=2023)
    p2 = Paper(title="HumanEval: Evaluating Large Language Models Trained on Code", year=2021)
    assert PaperDeduplicator.are_duplicates(p1, p2) is False


def test_merge_two_papers(sample_arxiv_paper, sample_s2_paper):
    """Verify metadata merging retains sources, higher citations, and longest abstract."""
    merged = PaperDeduplicator.merge_two_papers(sample_arxiv_paper, sample_s2_paper)
    # Check sources merged
    assert len(merged.sources) == 2
    providers = {s.provider for s in merged.sources}
    assert providers == {"arxiv", "semantic_scholar"}
    # Check max citation count retained
    assert merged.citation_count == 135
    # Check abstract is longest
    assert "comprehensive metrics" in merged.abstract


def test_deduplicate_list(sample_arxiv_paper, sample_s2_paper):
    """Verify deduplicating a list reduces duplicates and merges metadata."""
    p3 = Paper(title="Unique Paper on Code Generation", year=2024)
    paper_list = [sample_arxiv_paper, sample_s2_paper, p3]

    result = PaperDeduplicator.deduplicate(paper_list)
    assert len(result) == 2
    titles = {p.title for p in result}
    assert any("AgentBench" in t for t in titles)
    assert any("Unique Paper" in t for t in titles)

