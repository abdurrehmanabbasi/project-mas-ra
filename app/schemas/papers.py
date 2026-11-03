"""Paper and literature metadata schemas."""

import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class PaperSource(BaseModel):
    """Metadata specific to a retrieval provider (arXiv, Semantic Scholar)."""

    provider: str = Field(description="Name of provider, e.g. 'arxiv' or 'semantic_scholar'")
    provider_paper_id: str = Field(description="Unique paper ID according to the provider")
    url: Optional[str] = Field(default=None, description="Web landing page URL")
    pdf_url: Optional[str] = Field(default=None, description="Direct URL to PDF if accessible")


class Paper(BaseModel):
    """Canonical representation of an academic paper."""

    paper_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Internal canonical UUID for the paper",
    )
    title: str = Field(description="Normalized paper title")
    authors: List[str] = Field(default_factory=list, description="List of author names")
    year: Optional[int] = Field(default=None, description="Publication year")
    abstract: Optional[str] = Field(default=None, description="Abstract text if available")
    doi: Optional[str] = Field(default=None, description="Normalized Digital Object Identifier (DOI)")
    sources: List[PaperSource] = Field(
        default_factory=list,
        description="List of external provider sources where this paper was found",
    )
    citation_count: Optional[int] = Field(default=None, description="Reported citation count")
    relevance_score: Optional[float] = Field(
        default=0.0, description="Computed relevance score relative to search task"
    )


class PaperContent(BaseModel):
    """Retrieved and parsed paper content for analysis."""

    paper_id: str = Field(description="Canonical paper ID this content belongs to")
    text: str = Field(description="Raw text content extracted from abstract or full-text PDF")
    content_scope: str = Field(
        default="abstract_only",
        description="Scope of text: 'full_text', 'abstract_only', or 'metadata_only'",
    )
    retrieval_status: str = Field(
        default="success",
        description="Status of content retrieval: 'success', 'partial', or 'failed'",
    )
    file_size_bytes: Optional[int] = Field(default=None, description="Size in bytes of raw PDF")

