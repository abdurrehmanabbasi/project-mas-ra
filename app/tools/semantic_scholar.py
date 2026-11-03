"""Semantic Scholar Academic Graph API integration tool."""

import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.config import get_settings
from app.schemas.papers import Paper, PaperSource

logger = logging.getLogger(__name__)


class SemanticScholarTool:
    """Academic search tool querying the Semantic Scholar Academic Graph API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: Optional[int] = None):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.SEMANTIC_SCHOLAR_API_KEY
        self.timeout = timeout_seconds or settings.SEARCH_TIMEOUT_SECONDS

    def search(
        self,
        query: str,
        max_results: int = 10,
        date_range: Optional[Tuple[Optional[int], Optional[int]]] = None,
    ) -> List[Paper]:
        """Search Semantic Scholar for papers matching query.

        Args:
            query: Free text search keywords.
            max_results: Max papers to return (default: 10, max: 100).
            date_range: Optional tuple of (start_year, end_year).

        Returns:
            List of normalized Paper schemas.
        """
        headers: Dict[str, str] = {
            "User-Agent": "MAS-Research-Assistant/1.0",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key

        params: Dict[str, Any] = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": (
                "paperId,title,abstract,year,authors,externalIds,citationCount,openAccessPdf,url"
            ),
        }

        # Date range parameter if provided
        if date_range:
            start_yr, end_yr = date_range
            if start_yr and end_yr:
                params["year"] = f"{start_yr}-{end_yr}"
            elif start_yr:
                params["year"] = f"{start_yr}-"
            elif end_yr:
                params["year"] = f"-{end_yr}"

        # Retry logic with exponential backoff for HTTP 429
        max_retries = 3
        backoff_base = 2.0

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(self.BASE_URL, params=params, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    raw_papers = data.get("data", [])
                    return self._normalize_results(raw_papers)

                elif response.status_code == 429:
                    sleep_time = (backoff_base ** (attempt + 1)) + random.uniform(0.5, 1.5)
                    logger.warning(
                        f"Semantic Scholar 429 rate limit hit. Backing off for {sleep_time:.1f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(sleep_time)
                    continue

                else:
                    logger.error(
                        f"Semantic Scholar query failed with status {response.status_code}: {response.text[:200]}"
                    )
                    return []

            except httpx.RequestError as exc:
                logger.warning(f"Semantic Scholar connection error on attempt {attempt + 1}: {exc}")
                time.sleep(1.0)

        logger.error(f"Semantic Scholar queries exhausted retries for '{query}'")
        return []

    def _normalize_results(self, raw_papers: List[Dict[str, Any]]) -> List[Paper]:
        """Convert Semantic Scholar API response records into canonical Paper objects."""
        papers: List[Paper] = []
        for item in raw_papers:
            paper_id = item.get("paperId")
            title = item.get("title")
            if not paper_id or not title:
                continue

            # Extract DOI from externalIds if present
            external_ids = item.get("externalIds") or {}
            doi = external_ids.get("DOI") or external_ids.get("doi")

            # Extract open access PDF link
            oa_pdf = item.get("openAccessPdf") or {}
            pdf_url = oa_pdf.get("url")

            # Authors
            authors = [
                a["name"] for a in item.get("authors", []) if isinstance(a, dict) and a.get("name")
            ]

            source = PaperSource(
                provider="semantic_scholar",
                provider_paper_id=paper_id,
                url=item.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}",
                pdf_url=pdf_url,
            )

            paper = Paper(
                title=title.strip(),
                authors=authors,
                year=item.get("year"),
                abstract=item.get("abstract"),
                doi=doi,
                sources=[source],
                citation_count=item.get("citationCount"),
                relevance_score=1.0,
            )
            papers.append(paper)

        return papers

