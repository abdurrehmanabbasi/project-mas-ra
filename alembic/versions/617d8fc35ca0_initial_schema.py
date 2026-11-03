"""initial_schema

Revision ID: 617d8fc35ca0
Revises: 
Create Date: 2026-11-04 02:53:55.035502

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '617d8fc35ca0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create projects, research_runs, and reports tables."""
    # Projects Table
    op.create_table(
        'projects',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('research_question', sa.Text(), nullable=False),
        sa.Column('scope_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Research Runs Table
    op.create_table(
        'research_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('thread_id', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='queued'),
        sa.Column('current_phase', sa.String(length=100), nullable=False, server_default='initializing'),
        sa.Column('papers_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('evidence_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scope_json', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('thread_id')
    )

    # Reports Table
    op.create_table(
        'reports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('report_json', sa.Text(), nullable=False),
        sa.Column('markdown_content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['research_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema: drop reports, research_runs, and projects tables."""
    op.drop_table('reports')
    op.drop_table('research_runs')
    op.drop_table('projects')
