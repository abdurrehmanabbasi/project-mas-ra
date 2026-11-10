"""Database checkpointer factory managing PostgreSQL and persistent SQLite-backed checkpointers."""

import json
import logging
import socket
import sqlite3
import threading
from typing import Any, Optional, Sequence
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
)
from langgraph.checkpoint.memory import MemorySaver

from app.config import get_settings

logger = logging.getLogger(__name__)

_shared_memory_saver: Optional[MemorySaver] = None
_shared_sqlite_saver: Optional["SQLiteMemorySaver"] = None


class SQLiteMemorySaver(MemorySaver):
    """Persistent LangGraph checkpointer backed by Python stdlib sqlite3.

    Preserves checkpoints, pending writes, and human-in-the-loop interrupts across
    application restarts without relying on binary C-extension database drivers.
    """

    def __init__(self, db_path: str = "research_checkpoints.db"):
        super().__init__()
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._init_and_load()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return super().__exit__(exc_type, exc_value, traceback)

    def _init_and_load(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cp_storage (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    cp_type TEXT NOT NULL,
                    cp_bytes BLOB NOT NULL,
                    meta_type TEXT NOT NULL,
                    meta_bytes BLOB NOT NULL,
                    parent_id TEXT,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cp_writes (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL,
                    checkpoint_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    write_idx INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    val_type TEXT NOT NULL,
                    val_bytes BLOB NOT NULL,
                    task_path TEXT NOT NULL,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cp_blobs (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    version_json TEXT NOT NULL,
                    val_type TEXT NOT NULL,
                    val_bytes BLOB NOT NULL,
                    PRIMARY KEY (thread_id, checkpoint_ns, channel, version_json)
                )
                """
            )
            self._conn.commit()

            for row in cur.execute(
                "SELECT thread_id, checkpoint_ns, checkpoint_id, cp_type, cp_bytes, meta_type, meta_bytes, parent_id FROM cp_storage"
            ):
                tid, ns, cpid, cp_t, cp_b, m_t, m_b, parent = row
                self.storage[tid][ns][cpid] = ((cp_t, bytes(cp_b)), (m_t, bytes(m_b)), parent)

            for row in cur.execute(
                "SELECT thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx, channel, val_type, val_bytes, task_path FROM cp_writes"
            ):
                tid, ns, cpid, task_id, widx, ch, v_t, v_b, tpath = row
                self.writes[(tid, ns, cpid)][(task_id, widx)] = (
                    task_id,
                    ch,
                    (v_t, bytes(v_b)),
                    tpath,
                )

            for row in cur.execute(
                "SELECT thread_id, checkpoint_ns, channel, version_json, val_type, val_bytes FROM cp_blobs"
            ):
                tid, ns, ch, ver_json, v_t, v_b = row
                ver = json.loads(ver_json)
                self.blobs[(tid, ns, ch, ver)] = (v_t, bytes(v_b))

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        with self._lock:
            result = super().put(config, checkpoint, metadata, new_versions)
            thread_id = config["configurable"]["thread_id"]
            checkpoint_ns = config["configurable"]["checkpoint_ns"]
            checkpoint_id = checkpoint["id"]

            cp_typed, meta_typed, parent_id = self.storage[thread_id][checkpoint_ns][checkpoint_id]
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO cp_storage
                (thread_id, checkpoint_ns, checkpoint_id, cp_type, cp_bytes, meta_type, meta_bytes, parent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    cp_typed[0],
                    sqlite3.Binary(cp_typed[1]),
                    meta_typed[0],
                    sqlite3.Binary(meta_typed[1]),
                    parent_id,
                ),
            )
            for k, v in new_versions.items():
                blob_typed = self.blobs[(thread_id, checkpoint_ns, k, v)]
                cur.execute(
                    """
                    INSERT OR REPLACE INTO cp_blobs
                    (thread_id, checkpoint_ns, channel, version_json, val_type, val_bytes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        thread_id,
                        checkpoint_ns,
                        k,
                        json.dumps(v),
                        blob_typed[0],
                        sqlite3.Binary(blob_typed[1]),
                    ),
                )
            self._conn.commit()
            return result

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        with self._lock:
            super().put_writes(config, writes, task_id, task_path)
            thread_id = config["configurable"]["thread_id"]
            checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
            checkpoint_id = config["configurable"]["checkpoint_id"]
            outer_key = (thread_id, checkpoint_ns, checkpoint_id)
            cur = self._conn.cursor()
            for idx, (c, _) in enumerate(writes):
                inner_key = (task_id, WRITES_IDX_MAP.get(c, idx))
                stored_write = self.writes.get(outer_key, {}).get(inner_key)
                if stored_write is None:
                    continue
                t_id, ch, val_typed, t_path = stored_write
                cur.execute(
                    """
                    INSERT OR REPLACE INTO cp_writes
                    (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx, channel, val_type, val_bytes, task_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        thread_id,
                        checkpoint_ns,
                        checkpoint_id,
                        t_id,
                        inner_key[1],
                        ch,
                        val_typed[0],
                        sqlite3.Binary(val_typed[1]),
                        t_path,
                    ),
                )
            self._conn.commit()

    def delete_thread(self, thread_id: str) -> None:
        with self._lock:
            super().delete_thread(thread_id)
            cur = self._conn.cursor()
            cur.execute("DELETE FROM cp_storage WHERE thread_id = ?", (thread_id,))
            cur.execute("DELETE FROM cp_writes WHERE thread_id = ?", (thread_id,))
            cur.execute("DELETE FROM cp_blobs WHERE thread_id = ?", (thread_id,))
            self._conn.commit()


def _is_postgres_available(host: str = "localhost", port: int = 5432, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_checkpointer(
    force_memory: bool = False, conn_string: Optional[str] = None
) -> BaseCheckpointSaver:
    """Return an active checkpointer instance (PostgresSaver if reachable, else SQLite/MemorySaver).

    Args:
        force_memory: Explicitly force pure in-memory MemorySaver (useful for isolated unit tests).
        conn_string: Optional database URI override.

    Returns:
        BaseCheckpointSaver instance.
    """
    global _shared_memory_saver, _shared_sqlite_saver

    if _shared_memory_saver is None:
        _shared_memory_saver = MemorySaver()

    if force_memory:
        return _shared_memory_saver

    settings = get_settings()
    db_url = conn_string or settings.DATABASE_URL

    # Test mode safety: keep test runs isolated in RAM
    if settings.APP_ENV == "testing":
        return _shared_memory_saver

    # Explicit PostgreSQL check only when configured and reachable
    if db_url and "postgres" in db_url.lower() and _is_postgres_available():
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            clean_url = db_url.replace("postgresql+psycopg://", "postgresql://")
            saver = PostgresSaver.from_conn_string(clean_url)
            saver.setup()
            logger.info(f"Connected to PostgreSQL checkpointer at {clean_url.split('@')[-1]}")
            return saver
        except Exception as e:
            logger.debug(f"PostgreSQL checkpointer setup failed: {e}. Falling back to SQLite checkpointer.")

    if _shared_sqlite_saver is None:
        _shared_sqlite_saver = SQLiteMemorySaver("research_checkpoints.db")
    return _shared_sqlite_saver
