"""Database checkpointer factory managing PostgreSQL and in-memory fallback checkpointers."""

import logging
import socket
from typing import Optional
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from app.config import get_settings

logger = logging.getLogger(__name__)

_shared_memory_saver: Optional[MemorySaver] = None


def _is_postgres_available(host: str = "localhost", port: int = 5432, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


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

    if _shared_memory_saver is None:
        _shared_memory_saver = MemorySaver()

    if force_memory:
        return _shared_memory_saver

    settings = get_settings()
    db_url = conn_string or settings.DATABASE_URL

    # Test mode safety: if running tests, default to MemorySaver
    if settings.APP_ENV == "testing":
        return _shared_memory_saver

    # Pre-check if PostgreSQL is listening on port 5432
    if not _is_postgres_available():
        return _shared_memory_saver

    try:
        clean_url = db_url.replace("postgresql+psycopg://", "postgresql://")
        saver = PostgresSaver.from_conn_string(clean_url)
        saver.setup()
        logger.info(f"Connected to PostgreSQL checkpointer at {clean_url.split('@')[-1]}")
        return saver
    except Exception as e:
        logger.debug(f"PostgreSQL checkpointer setup failed: {e}. Using shared in-memory checkpointer.")
        return _shared_memory_saver

