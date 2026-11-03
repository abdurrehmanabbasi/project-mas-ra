"""Deterministic paper deduplication and source merging engine."""

import re
from typing import List, Optional, Set
from app.schemas.papers import Paper, PaperSource


class PaperDeduplicator:
    """Deduplicates academic papers across multiple providers (arXiv, Semantic Scholar)."""

    @staticmethod
    def normalize_doi(doi: Optional[str]) -> Optional[str]:
        """Normalize a DOI string to a standard lowercase form."""
        if not doi:
            return None
        cleaned = doi.strip().lower()
        cleaned = re.sub(r"^https?://(dx\.)?doi\.org/", "", cleaned)
        cleaned = re.sub(r"^doi:", "", cleaned)
        cleaned = cleaned.strip()
        return cleaned if cleaned else None

    @staticmethod
    def normalize_title(title: str) -> str:
        """Normalize paper title for fuzzy comparison by removing punctuation and extra whitespace."""
        if not title:
            return ""
        # Lowercase and remove punctuation / non-alphanumeric except spaces
        cleaned = re.sub(r"[^\w\s]", " ", title.lower())
        # Collapse multiple whitespace
        return re.sub(r"\s+", " ", cleaned).strip()

    @classmethod
    def are_duplicates(cls, p1: Paper, p2: Paper) -> bool:
        """Determine if two paper records refer to the same publication."""
        # 1. Check exact DOI match if both exist
        doi1 = cls.normalize_doi(p1.doi)
        doi2 = cls.normalize_doi(p2.doi)
        if doi1 and doi2:
            return doi1 == doi2

        # 2. Check provider-specific ID match if both share the same provider
        sources1 = {s.provider: s.provider_paper_id for s in p1.sources}
        sources2 = {s.provider: s.provider_paper_id for s in p2.sources}
        shared_providers = set(sources1.keys()) & set(sources2.keys())
        for provider in shared_providers:
            if sources1[provider] and sources2[provider]:
                if sources1[provider].lower() == sources2[provider].lower():
                    return True

        # 3. Check normalized title exact match
        t1 = cls.normalize_title(p1.title)
        t2 = cls.normalize_title(p2.title)
        if t1 and t2 and t1 == t2:
            # If both have years, allow +-1 year variance (preprint vs published)
            if p1.year and p2.year:
                if abs(p1.year - p2.year) <= 1:
                    return True
            else:
                return True

        # 4. Check token overlap Jaccard similarity for near-identical titles
        words1 = set(t1.split())
        words2 = set(t2.split())
        if words1 and words2:
            jaccard = len(words1 & words2) / len(words1 | words2)
            if jaccard > 0.85:
                if p1.year and p2.year:
                    if abs(p1.year - p2.year) <= 1:
                        return True
                else:
                    return True

        return False

    @classmethod
    def merge_two_papers(cls, primary: Paper, secondary: Paper) -> Paper:
        """Merge metadata from two duplicate paper records into a canonical Paper."""
        # Merge sources preserving uniqueness
        existing_sources = {(s.provider, s.provider_paper_id) for s in primary.sources}
        merged_sources = list(primary.sources)
        for s in secondary.sources:
            if (s.provider, s.provider_paper_id) not in existing_sources:
                merged_sources.append(s)
                existing_sources.add((s.provider, s.provider_paper_id))

        # Prefer longest / more complete abstract
        abstract = primary.abstract
        if not abstract or (secondary.abstract and len(secondary.abstract) > len(abstract)):
            abstract = secondary.abstract

        # Prefer non-null DOI
        doi = cls.normalize_doi(primary.doi) or cls.normalize_doi(secondary.doi)

        # Merge authors
        author_names = list(primary.authors)
        primary_lower = {a.lower() for a in author_names}
        for a in secondary.authors:
            if a.lower() not in primary_lower:
                author_names.append(a)
                primary_lower.add(a.lower())

        # Citation count: take maximum reported
        citations = None
        if primary.citation_count is not None or secondary.citation_count is not None:
            c1 = primary.citation_count or 0
            c2 = secondary.citation_count or 0
            citations = max(c1, c2)

        # Year: prefer primary or secondary
        year = primary.year or secondary.year

        # Relevance score: take highest
        rel_score = max(primary.relevance_score or 0.0, secondary.relevance_score or 0.0)

        return Paper(
            paper_id=primary.paper_id,
            title=primary.title if len(primary.title) >= len(secondary.title) else secondary.title,
            authors=author_names,
            year=year,
            abstract=abstract,
            doi=doi,
            sources=merged_sources,
            citation_count=citations,
            relevance_score=rel_score,
        )

    @classmethod
    def deduplicate(cls, papers: List[Paper]) -> List[Paper]:
        """Deduplicate a list of Paper objects, merging duplicate records."""
        unique_papers: List[Paper] = []

        for candidate in papers:
            matched_index = -1
            for i, existing in enumerate(unique_papers):
                if cls.are_duplicates(existing, candidate):
                    matched_index = i
                    break

            if matched_index >= 0:
                unique_papers[matched_index] = cls.merge_two_papers(
                    unique_papers[matched_index], candidate
                )
            else:
                unique_papers.append(candidate)

        return unique_papers

