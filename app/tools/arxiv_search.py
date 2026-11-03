"""arXiv API integration tool for academic preprint search."""

import logging
import re
import time
from typing import List, Optional, Tuple
import arxiv

from app.config import get_settings
from app.schemas.papers import Paper, PaperSource

logger = logging.getLogger(__name__)


class ArxivSearchTool:
    """Academic search tool querying the arXiv API with rate limiting and schema normalization."""

    def __init__(self, request_delay: Optional[float] = None):
        settings = get_settings()
        self.delay = (
            request_delay
            if request_delay is not None
            else settings.ARXIV_REQUEST_DELAY_SECONDS
        )
        self.last_request_time = 0.0
        self.client = arxiv.Client(
            page_size=20,
            delay_seconds=self.delay,
            num_retries=3,
        )

    def _rate_limit(self) -> None:
        """Enforce polite spacing between requests."""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def search(
        self,
        query: str,
        max_results: int = 10,
        date_range: Optional[Tuple[Optional[int], Optional[int]]] = None,
    ) -> List[Paper]:
        """Search arXiv for preprints matching the query string.

        Args:
            query: Free-text search terms or arXiv boolean query.
            max_results: Max papers to return.
            date_range: Optional tuple of (start_year, end_year).

        Returns:
            List of normalized Paper schemas.
        """
        self._rate_limit()

        # Build clean search object
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )

        results: List[Paper] = []
        try:
            for entry in self.client.results(search):
                year = entry.published.year if entry.published else None

                # Apply date filter if specified
                if date_range:
                    start_yr, end_yr = date_range
                    if start_yr and year and year < start_yr:
                        continue
                    if end_yr and year and year > end_yr:
                        continue

                # Extract arXiv short identifier (e.g. 2305.12345)
                arxiv_id = entry.entry_id.split("/abs/")[-1]

                paper_source = PaperSource(
                    provider="arxiv",
                    provider_paper_id=arxiv_id,
                    url=entry.entry_id,
                    pdf_url=entry.pdf_url,
                )

                # Clean abstract (remove newlines in mid-sentence)
                cleaned_abstract = None
                if entry.summary:
                    cleaned_abstract = re.sub(r"\s+", " ", entry.summary).strip()

                paper = Paper(
                    title=entry.title.strip(),
                    authors=[a.name for a in entry.authors] if entry.authors else [],
                    year=year,
                    abstract=cleaned_abstract,
                    doi=entry.doi,
                    sources=[paper_source],
                    citation_count=None,
                    relevance_score=1.0,
                )
                results.append(paper)

        except Exception as e:
            logger.error(f"Error during arXiv query '{query}': {e}", exc_info=True)

        return results

