"""Pydantic data contract schemas for research, papers, evidence, and reports."""

from app.schemas.api import (
    HumanReviewDecision,
    ProjectCreateRequest,
    ProjectResponse,
    RunStartRequest,
    RunStatusResponse,
)
from app.schemas.evidence import (
    Critique,
    Evidence,
    PaperAnalysis,
    ResearchSynthesis,
)
from app.schemas.papers import (
    Paper,
    PaperContent,
    PaperSource,
)
from app.schemas.report import (
    CitationCheck,
    ReportSection,
    ResearchReport,
)
from app.schemas.research import (
    ResearchPlan,
    ResearchScope,
    ResearchTask,
)

__all__ = [
    "Paper",
    "PaperSource",
    "PaperContent",
    "ResearchScope",
    "ResearchTask",
    "ResearchPlan",
    "Evidence",
    "PaperAnalysis",
    "ResearchSynthesis",
    "Critique",
    "CitationCheck",
    "ReportSection",
    "ResearchReport",
    "ProjectCreateRequest",
    "ProjectResponse",
    "RunStartRequest",
    "RunStatusResponse",
    "HumanReviewDecision",
]

