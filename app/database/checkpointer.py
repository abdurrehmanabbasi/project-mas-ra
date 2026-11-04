"""Database checkpointer factory managing PostgreSQL and in-memory fallback checkpointers."""

import logging
from typing import Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from app.config import get_settings

logger = logging.getLogger(__name__)

_shared_memory_saver: Optional[MemorySaver] = None


def get_checkpointer(
    force_memory: bool = False, conn_string: Optional[str] = None
) -> BaseCheckpointSaver:
    """Return an active checkpointer instance (PostgresSaver if reachable, else MemorySaver).

    Args:
        force_memory: Explicitly force MemorySaver (useful for isolated unit tests).
        conn_string: Optional database URI override.

    Returns:
        BaseCheckpointSaver (PostgresSaver or MemorySaver).
    """
    global _shared_memory_saver

    if force_memory:
        return MemorySaver()

    settings = get_settings()
    db_url = conn_string or settings.DATABASE_URL

    # Test mode safety: if running tests, default to MemorySaver
    if settings.APP_ENV == "testing":
        return MemorySaver()

    try:
        # Normalize URI format for psycopg driver
        clean_url = db_url.replace("postgresql+psycopg://", "postgresql://")
        saver = PostgresSaver.from_conn_string(clean_url)
        saver.setup()
        logger.info(f"Connected to PostgreSQL checkpointer at {clean_url.split('@')[-1]}")
        return saver
    except Exception as e:
        logger.warning(
            f"Could not connect to PostgreSQL checkpointer ({e}). Falling back to in-memory checkpointer (MemorySaver)."
        )
        if _shared_memory_saver is None:
            _shared_memory_saver = MemorySaver()
        return _shared_memory_saver

