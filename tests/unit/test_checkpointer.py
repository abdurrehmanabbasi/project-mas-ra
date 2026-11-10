"""Unit tests for checkpointer factory."""

from typing import TypedDict
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from app.database.checkpointer import SQLiteMemorySaver, get_checkpointer


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


def test_sqlite_checkpointer_persists_interrupt_across_restart(tmp_path):
    """Verify SQLiteMemorySaver persists interrupted graph state across instance restarts."""
    class _MiniState(TypedDict):
        val: str

    def _hitl_node(state: _MiniState):
        decision = interrupt({"prompt": "approve?"})
        return {"val": f"{state['val']}-{decision['action']}"}

    db_path = str(tmp_path / "cp_persist.db")

    builder1 = StateGraph(_MiniState)
    builder1.add_node("hitl", _hitl_node)
    builder1.add_edge(START, "hitl")
    builder1.add_edge("hitl", END)
    saver1 = SQLiteMemorySaver(db_path)
    g1 = builder1.compile(checkpointer=saver1)

    cfg = {"configurable": {"thread_id": "persist-thread-1"}}
    g1.invoke({"val": "start"}, config=cfg)
    assert g1.get_state(cfg).next == ("hitl",)
    saver1.close()

    # Recreate graph with fresh SQLiteMemorySaver pointing at the same SQLite file
    builder2 = StateGraph(_MiniState)
    builder2.add_node("hitl", _hitl_node)
    builder2.add_edge(START, "hitl")
    builder2.add_edge("hitl", END)
    saver2 = SQLiteMemorySaver(db_path)
    g2 = builder2.compile(checkpointer=saver2)

    assert g2.get_state(cfg).next == ("hitl",)
    final_state = g2.invoke(Command(resume={"action": "approved"}), config=cfg)
    assert final_state["val"] == "start-approved"
    saver2.close()

