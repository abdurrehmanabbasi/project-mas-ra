"""Citation verification and final research report schemas."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CitationCheck(BaseModel):
    """Validation record for a cited paper and its claim links."""

    citation_id: str = Field(
        default_factory=lambda: f"cit-{uuid.uuid4().hex[:8]}",
        description="Unique citation validation record ID",
    )
    paper_id: str = Field(description="Canonical ID of the referenced paper")
    doi_valid: bool = Field(default=True, description="Whether the DOI exists and is valid")
    url_accessible: bool = Field(default=True, description="Whether the paper link is reachable")
    claim_supported: bool = Field(
        default=True, description="Whether the referenced evidence supports the claim"
    )
    notes: Optional[str] = Field(default=None, description="Verification notes or discrepancy reason")


class ReportSection(BaseModel):
    """A thematic section in the literature review report."""

    title: str = Field(description="Section heading")
    content: str = Field(description="Markdown content with citations")
    evidence_ids: List[str] = Field(
        default_factory=list, description="Associated evidence records used"
    )


class ResearchReport(BaseModel):
    """Comprehensive literature review report output."""

    report_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique report identifier",
    )
    project_id: str = Field(description="Associated project ID")
    title: str = Field(description="Formal literature review title")
    abstract: str = Field(description="Executive summary abstract")
    introduction: str = Field(description="Context and motivation")
    sections: List[ReportSection] = Field(
        default_factory=list, description="Thematic and analytical sections"
    )
    comparative_analysis: str = Field(description="Cross-paper synthesis and matrix comparison")
    research_gaps: List[str] = Field(
        default_factory=list, description="Identified open challenges and future directions"
    )
    limitations: str = Field(description="Threats to validity, search boundaries, and coverage limits")
    references: List[Dict[str, Any]] = Field(
        default_factory=list, description="Complete bibliography formatted with DOIs and links"
    )
    citation_checks: List[CitationCheck] = Field(
        default_factory=list, description="Verification results for all citations"
    )

