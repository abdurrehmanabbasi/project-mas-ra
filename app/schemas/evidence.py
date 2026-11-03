"""Evidence extraction, paper analysis, and literature critique schemas."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """An atomic, grounded evidence passage extracted from a paper."""

    evidence_id: str = Field(
        default_factory=lambda: f"ev-{uuid.uuid4().hex[:8]}",
        description="Unique identifier for the evidence excerpt",
    )
    paper_id: str = Field(description="Canonical ID of the paper providing this evidence")
    evidence_type: str = Field(
        default="finding",
        description="Category: 'finding', 'methodology', 'limitation', or 'benchmark'",
    )
    claim: str = Field(description="The factual claim or assertion supported by this excerpt")
    supporting_passage: str = Field(
        description="Verbatim or close textual excerpt from the source document"
    )
    section: Optional[str] = Field(default=None, description="Section heading (e.g. 'Methods')")
    page: Optional[int] = Field(default=None, description="Page number where available")
    content_scope: str = Field(
        default="abstract_only",
        description="Provenance scope: 'full_text' or 'abstract_only'",
    )
    extraction_confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score of evidence grounding"
    )


class PaperAnalysis(BaseModel):
    """Structured extraction of methodology, findings, and limits from one paper."""

    paper_id: str = Field(description="Canonical paper ID")
    methodology: str = Field(description="Summary of approach, models, or algorithms used")
    datasets_used: List[str] = Field(default_factory=list, description="Benchmarks or datasets")
    findings: List[str] = Field(default_factory=list, description="Key empirical findings")
    limitations: List[str] = Field(default_factory=list, description="Reported threats to validity")
    evidence_ids: List[str] = Field(
        default_factory=list, description="IDs of supporting Evidence items"
    )


class ResearchSynthesis(BaseModel):
    """Cross-paper comparative analysis."""

    themes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Synthesized thematic clusters"
    )
    comparisons: List[Dict[str, Any]] = Field(
        default_factory=list, description="Direct comparisons between methodologies or results"
    )
    disagreements: List[Dict[str, Any]] = Field(
        default_factory=list, description="Contradictions or conflicting findings in literature"
    )
    research_gaps: List[str] = Field(
        default_factory=list, description="Open problems and unaddressed questions identified"
    )


class Critique(BaseModel):
    """Automated assessment of literature coverage and synthesis quality."""

    quality_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Overall coverage and quality rating"
    )
    missing_topics: List[str] = Field(
        default_factory=list, description="Identified subquestions needing more literature"
    )
    unsupported_claims: List[str] = Field(
        default_factory=list, description="Claims lacking sufficient evidence backing"
    )
    needs_revision: bool = Field(
        default=False, description="Flag indicating if another search iteration is required"
    )
    suggested_revision_tasks: List[str] = Field(
        default_factory=list, description="Targeted query suggestions for revision worker"
    )

