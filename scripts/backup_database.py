"""Database backup script: exports projects, runs, and reports into a timestamped JSON archive."""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.service import DatabaseService, get_db_session
from app.database.models import ProjectModel, ResearchRunModel, ReportModel


def backup_database(output_dir: str = "backups") -> str:
    """Export all database tables into a structured backup JSON archive."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(output_dir, f"backup_{timestamp}.json")

    session = get_db_session()
    try:
        projects = session.query(ProjectModel).all()
        runs = session.query(ResearchRunModel).all()
        reports = session.query(ReportModel).all()

        backup_payload = {
            "metadata": {
                "timestamp": timestamp,
                "version": "1.0",
                "counts": {
                    "projects": len(projects),
                    "runs": len(runs),
                    "reports": len(reports),
                },
            },
            "projects": [
                {
                    "id": p.id,
                    "title": p.title,
                    "research_question": p.research_question,
                    "scope_json": p.scope_json,
                    "status": p.status,
                    "created_at": p.created_at.isoformat(),
                    "updated_at": p.updated_at.isoformat(),
                }
                for p in projects
            ],
            "research_runs": [
                {
                    "id": r.id,
                    "project_id": r.project_id,
                    "thread_id": r.thread_id,
                    "status": r.status,
                    "current_phase": r.current_phase,
                    "papers_count": r.papers_count,
                    "evidence_count": r.evidence_count,
                    "scope_json": r.scope_json,
                    "error_message": r.error_message,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                }
                for r in runs
            ],
            "reports": [
                {
                    "id": rep.id,
                    "project_id": rep.project_id,
                    "run_id": rep.run_id,
                    "title": rep.title,
                    "report_json": rep.report_json,
                    "markdown_content": rep.markdown_content,
                    "created_at": rep.created_at.isoformat(),
                }
                for rep in reports
            ],
        }

        with open(backup_file, "w", encoding="utf-8") as f:
            json.dump(backup_payload, f, indent=2)

        print(f"[OK] Database successfully backed up to: {backup_file}")
        return backup_file
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backup research database.")
    parser.add_argument("--output-dir", type=str, default="backups", help="Target backup directory")
    args = parser.parse_args()
    backup_database(args.output_dir)
