"""API request and response schemas for FastAPI endpoints."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.research import ResearchScope


class ProjectCreateRequest(BaseModel):
    """Payload to create a new research project."""

    title: str = Field(min_length=3, description="User-facing project name")
    research_question: str = Field(min_length=10, description="The central research inquiry")
    scope: Optional[ResearchScope] = Field(default_factory=ResearchScope)


class ProjectResponse(BaseModel):
    """Project metadata summary."""

    project_id: str
    title: str
    research_question: str
    status: str
    created_at: str


class RunStartRequest(BaseModel):
    """Request payload to initiate a new research run."""

    scope_override: Optional[ResearchScope] = None


class RunStatusResponse(BaseModel):
    """Current execution status of a research run."""

    run_id: str
    project_id: str
    status: str  # queued, running, waiting_for_review, completed, failed, cancelled
    current_phase: str
    papers_found: int = 0
    evidence_count: int = 0
    error_message: Optional[str] = None


class HumanReviewDecision(BaseModel):
    """User decision submitted during human approval checkpoint."""

    action: str = Field(description="'approve', 'request_revision', or 'reject'")
    feedback: Optional[str] = Field(
        default=None, description="Specific feedback or focus instructions if requesting revision"
    )

