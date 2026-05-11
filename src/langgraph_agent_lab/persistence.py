"""Checkpointer adapter.

Supports: memory (default), sqlite (extension), none (testing without persistence).

Usage:
    # Memory (default, no infra needed)
    cp = build_checkpointer("memory")

    # SQLite (extension track - survives process restart)
    with build_checkpointer_ctx("sqlite", "checkpoints.db") as cp:
        graph = build_graph(checkpointer=cp)
        ...
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any


def build_checkpointer(kind: str = "memory", database_url: str | None = None) -> Any | None:  # noqa: ANN401
    """Return a LangGraph checkpointer instance.

    For SQLite, prefer build_checkpointer_ctx() to ensure the connection
    is properly closed. This function works for memory and none only.
    """
    if kind == "none":
        return None
    if kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
    if kind == "sqlite":
        # SqliteSaver v3+ requires context manager — delegate to build_checkpointer_ctx
        raise ValueError(
            "For SQLite, use build_checkpointer_ctx() as a context manager. "
            "Example: with build_checkpointer_ctx('sqlite') as cp: ..."
        )
    if kind == "postgres":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            raise RuntimeError(
                "Postgres checkpointer requires: pip install langgraph-checkpoint-postgres"
            ) from exc
        return PostgresSaver.from_conn_string(database_url or "")
    raise ValueError(f"Unknown checkpointer kind: {kind!r}")


@contextmanager
def build_checkpointer_ctx(
    kind: str = "memory",
    database_url: str | None = None,
) -> Generator[Any, None, None]:
    """Context manager that yields a checkpointer and cleans up on exit.

    Works for all checkpointer types including SQLite.

    Example:
        with build_checkpointer_ctx("sqlite", "checkpoints.db") as cp:
            graph = build_graph(checkpointer=cp)
            result = graph.invoke(state, config=run_config)
    """
    if kind == "none":
        yield None
    elif kind == "memory":
        from langgraph.checkpoint.memory import MemorySaver
        yield MemorySaver()
    elif kind == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ImportError as exc:
            raise RuntimeError(
                "SQLite checkpointer requires: pip install langgraph-checkpoint-sqlite"
            ) from exc
        db_path = database_url or "checkpoints.db"
        with SqliteSaver.from_conn_string(db_path) as cp:
            yield cp
    elif kind == "postgres":
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
        except ImportError as exc:
            raise RuntimeError(
                "Postgres checkpointer requires: pip install langgraph-checkpoint-postgres"
            ) from exc
        with PostgresSaver.from_conn_string(database_url or "") as cp:
            yield cp
    else:
        raise ValueError(f"Unknown checkpointer kind: {kind!r}")
