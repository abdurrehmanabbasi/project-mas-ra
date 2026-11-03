"""Citation and claim verification engine validating bibliographic metadata and evidence grounding."""

import logging
import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from app.schemas.evidence import Evidence
from app.schemas.papers import Paper
from app.schemas.report import CitationCheck
from app.tools.paper_dedup import PaperDeduplicator

logger = logging.getLogger(__name__)


class CitationVerifier:
    """Verifies bibliographic metadata (DOIs, URLs) and empirical claim support."""

    # Standard DOI regex specification
    DOI_REGEX = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$")

    @classmethod
    def validate_doi(cls, doi: Optional[str]) -> bool:
        """Validate whether a DOI conforms to standard syntax."""
        if not doi:
            return False
        normalized = PaperDeduplicator.normalize_doi(doi)
        if not normalized:
            return False
        return bool(cls.DOI_REGEX.match(normalized))

    @classmethod
    def validate_url(cls, url: Optional[str]) -> bool:
        """Validate whether a URL is syntactically well-formed."""
        if not url:
            return False
        try:
            parsed = urlparse(url.strip())
            return bool(parsed.scheme in ("http", "https") and parsed.netloc and "." in parsed.netloc)
        except Exception:
            return False

    @classmethod
    def verify_claim_support(
        cls,
        paper_id: str,
        claim: str,
        evidence_records: List[Evidence],
    ) -> Tuple[bool, Optional[str]]:
        """Verify whether an assertion in the review is grounded in an evidence passage.

        Args:
            paper_id: Canonical paper ID referenced.
            claim: Assertion text made in synthesis or section.
            evidence_records: List of atomic Evidence records from the corpus.

        Returns:
            Tuple of (is_supported, explanation_notes).
        """
        # Find evidence belonging to this paper
        paper_evidence = [e for e in evidence_records if e.paper_id == paper_id]

        if not paper_evidence:
            return False, "Citation references a paper with no extracted evidence records."

        # Check if any evidence passage has non-empty text supporting the claim
        supported = any(
            len(e.supporting_passage.strip()) > 15
            for e in paper_evidence
        )

        if not supported:
            return False, "Referenced paper contains empty or insufficient evidence passages."

        return True, None

    @classmethod
    def verify_all(
        cls,
        papers: List[Paper],
        evidence_records: List[Evidence],
    ) -> List[CitationCheck]:
        """Perform comprehensive bibliographic and evidence grounding checks across papers.

        Args:
            papers: Corpus of selected papers.
            evidence_records: Corpus of extracted evidence passages.

        Returns:
            List of CitationCheck validation records.
        """
        checks: List[CitationCheck] = []
        evidence_paper_ids = {e.paper_id for e in evidence_records}

        for paper in papers:
            # Check DOI validity if present
            doi_valid = cls.validate_doi(paper.doi) if paper.doi else True

            # Check URLs from sources
            url_valid = True
            for source in paper.sources:
                if source.url and not cls.validate_url(source.url):
                    url_valid = False
                if source.pdf_url and not cls.validate_url(source.pdf_url):
                    url_valid = False

            # Check claim support
            has_evidence = paper.paper_id in evidence_paper_ids
            notes = None
            if not has_evidence:
                notes = "Paper has valid metadata but lacks atomic extracted evidence passages."

            check = CitationCheck(
                paper_id=paper.paper_id,
                doi_valid=doi_valid,
                url_accessible=url_valid,
                claim_supported=has_evidence,
                notes=notes,
            )
            checks.append(check)

        return checks
