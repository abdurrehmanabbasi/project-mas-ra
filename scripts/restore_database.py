"""Database restoration script: restores projects, runs, and reports from a JSON backup archive."""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.service import get_db_session
from app.database.models import ProjectModel, ResearchRunModel, ReportModel


def restore_database(backup_file: str) -> None:
    """Restore database tables from a structured backup JSON archive."""
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    with open(backup_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    session = get_db_session()
    try:
        # Restore projects
        for p_dict in data.get("projects", []):
            existing = session.query(ProjectModel).filter(ProjectModel.id == p_dict["id"]).first()
            if not existing:
                p = ProjectModel(
                    id=p_dict["id"],
                    title=p_dict["title"],
                    research_question=p_dict["research_question"],
                    scope_json=p_dict.get("scope_json"),
                    status=p_dict.get("status", "active"),
                    created_at=datetime.datetime.fromisoformat(p_dict["created_at"]),
                    updated_at=datetime.datetime.fromisoformat(p_dict["updated_at"]),
                )
                session.add(p)

        # Restore runs
        for r_dict in data.get("research_runs", []):
            existing = session.query(ResearchRunModel).filter(ResearchRunModel.id == r_dict["id"]).first()
            if not existing:
                r = ResearchRunModel(
                    id=r_dict["id"],
                    project_id=r_dict["project_id"],
                    thread_id=r_dict["thread_id"],
                    status=r_dict.get("status", "queued"),
                    current_phase=r_dict.get("current_phase", "initialized"),
                    papers_count=r_dict.get("papers_count", 0),
                    evidence_count=r_dict.get("evidence_count", 0),
                    scope_json=r_dict.get("scope_json"),
                    error_message=r_dict.get("error_message"),
                    created_at=datetime.datetime.fromisoformat(r_dict["created_at"]),
                    updated_at=datetime.datetime.fromisoformat(r_dict["updated_at"]),
                )
                session.add(r)

        # Restore reports
        for rep_dict in data.get("reports", []):
            existing = session.query(ReportModel).filter(ReportModel.id == rep_dict["id"]).first()
            if not existing:
                rep = ReportModel(
                    id=rep_dict["id"],
                    project_id=rep_dict["project_id"],
                    run_id=rep_dict["run_id"],
                    title=rep_dict["title"],
                    report_json=rep_dict["report_json"],
                    markdown_content=rep_dict["markdown_content"],
                    created_at=datetime.datetime.fromisoformat(rep_dict["created_at"]),
                )
                session.add(rep)

        session.commit()
        print(f"[OK] Database successfully restored from: {backup_file}")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restore research database from backup archive.")
    parser.add_argument("backup_file", type=str, help="Path to backup JSON file")
    args = parser.parse_args()
    restore_database(args.backup_file)

