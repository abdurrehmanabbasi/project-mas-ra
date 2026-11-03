"""Unit tests for checkpointer factory."""

from langgraph.checkpoint.memory import MemorySaver
from app.database.checkpointer import get_checkpointer


def test_get_checkpointer_force_memory():
    """Verify force_memory=True returns MemorySaver."""
    cp = get_checkpointer(force_memory=True)
    assert isinstance(cp, MemorySaver)


def test_get_checkpointer_unreachable_db_fallback():
    """Verify that an unreachable database gracefully falls back to MemorySaver without crashing."""
    # Invalid port / host
    fake_conn = "postgresql://fake_user:fake_pass@localhost:59999/nonexistent_db"
    cp = get_checkpointer(force_memory=False, conn_string=fake_conn)
    assert isinstance(cp, MemorySaver)
