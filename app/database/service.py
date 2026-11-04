"""Database service layer providing engine lifecycle, session management, and CRUD helpers."""

import json
import logging
import socket
from typing import Any, Dict, List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.config import get_settings
from app.database.models import Base, ProjectModel, ReportModel, ResearchRunModel

logger = logging.getLogger(__name__)

_engine = None
_SessionFactory = None


def _is_postgres_available(host: str = "localhost", port: int = 5432, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_db_engine():
    """Retrieve or initialize the SQLAlchemy database engine."""
    global _engine, _SessionFactory
    if _engine is None:
        settings = get_settings()
        db_url = settings.DATABASE_URL

        # Quick pre-check: if URL specifies postgres, check if port 5432 is reachable
        if ("postgresql" in db_url or "psycopg" in db_url) and not _is_postgres_available():
            db_url = "sqlite:///./research.db"

        connect_args = {}
        if "sqlite" in db_url:
            connect_args["check_same_thread"] = False
        elif "postgresql" in db_url or "psycopg" in db_url:
            connect_args["connect_timeout"] = 1

        try:
            _engine = create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)
            with _engine.connect() as conn:
                pass
        except Exception as e:
            logger.info(f"Using SQLite local db (PostgreSQL unavailable: {e}).")
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
            return (
                session.query(ProjectModel)
                .options(selectinload(ProjectModel.runs))
                .order_by(ProjectModel.created_at.desc())
                .all()
            )
        finally:
            session.close()

    @classmethod
    def get_project(cls, project_id: str) -> Optional[ProjectModel]:
        session = get_db_session()
        try:
            return (
                session.query(ProjectModel)
                .options(selectinload(ProjectModel.runs))
                .filter(ProjectModel.id == project_id)
                .first()
            )
        finally:
            session.close()

    @classmethod
    def list_runs(cls) -> List[ResearchRunModel]:
        session = get_db_session()
        try:
            return session.query(ResearchRunModel).order_by(ResearchRunModel.created_at.desc()).all()
        finally:
            session.close()

    @classmethod
    def list_reports(cls) -> List[ReportModel]:
        session = get_db_session()
        try:
            return session.query(ReportModel).order_by(ReportModel.created_at.desc()).all()
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
