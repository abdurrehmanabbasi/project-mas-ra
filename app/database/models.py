"""SQLAlchemy declarative models for projects, research runs, and generated reports."""

import datetime
import uuid
from typing import Optional
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ProjectModel(Base):
    """Database record for a user research project."""

    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    research_question = Column(Text, nullable=False)
    scope_json = Column(Text, nullable=True)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    runs = relationship("ResearchRunModel", back_populates="project", cascade="all, delete-orphan")


class ResearchRunModel(Base):
    """Database record for an execution run of the LangGraph multi-agent engine."""

    __tablename__ = "research_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    thread_id = Column(String(100), unique=True, nullable=False)
    status = Column(String(50), default="queued", nullable=False)
    current_phase = Column(String(100), default="initializing", nullable=False)
    papers_count = Column(Integer, default=0, nullable=False)
    evidence_count = Column(Integer, default=0, nullable=False)
    scope_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    project = relationship("ProjectModel", back_populates="runs")
    reports = relationship("ReportModel", back_populates="run", cascade="all, delete-orphan")


class ReportModel(Base):
    """Database record for synthesized literature review reports."""

    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(String(36), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    report_json = Column(Text, nullable=False)
    markdown_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    run = relationship("ResearchRunModel", back_populates="reports")

