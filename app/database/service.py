"""Database service layer providing engine lifecycle, session management, and CRUD helpers."""

import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.models import Base, ProjectModel, ReportModel, ResearchRunModel

logger = logging.getLogger(__name__)

_engine = None
_SessionFactory = None


def get_db_engine():
    """Retrieve or initialize the SQLAlchemy database engine."""
    global _engine, _SessionFactory
    if _engine is None:
        settings = get_settings()
        db_url = settings.DATABASE_URL
        # Default to SQLite for zero-configuration local runs if postgres unreachable
        connect_args = {}
        if "sqlite" in db_url:
            connect_args["check_same_thread"] = False
        elif "postgresql" in db_url or "psycopg" in db_url:
            connect_args["connect_timeout"] = 1
        try:
            _engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
            # Test engine connection
            with _engine.connect() as conn:
                pass
        except Exception as e:
            logger.warning(f"Database connection to {db_url} failed: {e}. Falling back to SQLite local db.")
            sqlite_url = "sqlite:///./research.db"
            _engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

        # Initialize schema tables
        Base.metadata.create_all(_engine)
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_db_session() -> Session:
    """Yield a database session context."""
    get_db_engine()
    session = _SessionFactory()
    try:
        return session
    except Exception:
        session.close()
        raise


class DatabaseService:
    """Repository helper for managing projects, runs, and reports."""

    @classmethod
    def create_project(cls, title: str, research_question: str, scope: Optional[Dict[str, Any]] = None) -> ProjectModel:
        session = get_db_session()
        try:
            scope_str = json.dumps(scope) if scope else "{}"
            project = ProjectModel(
                title=title,
                research_question=research_question,
                scope_json=scope_str,
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            return project
        finally:
            session.close()

    @classmethod
    def list_projects(cls) -> List[ProjectModel]:
        session = get_db_session()
        try:
            return session.query(ProjectModel).order_by(ProjectModel.created_at.desc()).all()
        finally:
            session.close()

    @classmethod
    def get_project(cls, project_id: str) -> Optional[ProjectModel]:
        session = get_db_session()
        try:
            return session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        finally:
            session.close()

    @classmethod
    def create_run(cls, project_id: str, thread_id: str, scope_override: Optional[Dict[str, Any]] = None) -> ResearchRunModel:
        session = get_db_session()
        try:
            scope_str = json.dumps(scope_override) if scope_override else "{}"
            run = ResearchRunModel(
                project_id=project_id,
                thread_id=thread_id,
                status="queued",
                current_phase="initialized",
                scope_json=scope_str,
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run
        finally:
            session.close()

    @classmethod
    def update_run_status(
        cls,
        run_id: str,
        status: str,
        current_phase: Optional[str] = None,
        papers_count: Optional[int] = None,
        evidence_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[ResearchRunModel]:
        session = get_db_session()
        try:
            run = session.query(ResearchRunModel).filter(ResearchRunModel.id == run_id).first()
            if not run:
                return None
            run.status = status
            if current_phase:
                run.current_phase = current_phase
            if papers_count is not None:
                run.papers_count = papers_count
            if evidence_count is not None:
                run.evidence_count = evidence_count
            if error_message is not None:
                run.error_message = error_message
            session.commit()
            session.refresh(run)
            return run
        finally:
            session.close()

    @classmethod
    def get_run(cls, run_id: str) -> Optional[ResearchRunModel]:
        session = get_db_session()
        try:
            return session.query(ResearchRunModel).filter(ResearchRunModel.id == run_id).first()
        finally:
            session.close()

    @classmethod
    def save_report(cls, project_id: str, run_id: str, title: str, report_dict: Dict[str, Any], markdown_content: str) -> ReportModel:
        session = get_db_session()
        try:
            report = ReportModel(
                project_id=project_id,
                run_id=run_id,
                title=title,
                report_json=json.dumps(report_dict),
                markdown_content=markdown_content,
            )
            session.add(report)
            session.commit()
            session.refresh(report)
            return report
        finally:
            session.close()

    @classmethod
    def get_report_by_run(cls, run_id: str) -> Optional[ReportModel]:
        session = get_db_session()
        try:
            return session.query(ReportModel).filter(ReportModel.run_id == run_id).first()
        finally:
            session.close()
