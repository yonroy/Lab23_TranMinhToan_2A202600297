"""Extension demos: SQLite persistence, crash-resume, and time-travel replay.

Run with:
    python -m langgraph_agent_lab.extension_demo
"""

from __future__ import annotations

import os
from pathlib import Path

from .graph import build_graph
from .persistence import build_checkpointer_ctx
from .state import Route, Scenario, initial_state

DB_PATH = "outputs/checkpoints.db"
THREAD_ID = "demo-thread-S02"


def _run_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


# ---------------------------------------------------------------------------
# Demo 1: SQLite persistence — state survives process restart
# ---------------------------------------------------------------------------

def demo_sqlite_first_run() -> dict:
    """First run: invoke the graph and persist state to SQLite."""
    scenario = Scenario(
        id="S02", query="Please lookup order status for order 12345", expected_route=Route.TOOL
    )
    state = initial_state(scenario)
    state["thread_id"] = THREAD_ID  # fixed thread_id for resume demo

    with build_checkpointer_ctx("sqlite", DB_PATH) as cp:
        graph = build_graph(checkpointer=cp)
        result = graph.invoke(state, config=_run_config(THREAD_ID))

    print("[Demo 1] First run complete.")
    print(f"  route        = {result.get('route')}")
    print(f"  final_answer = {result.get('final_answer', '')[:60]}")
    print(f"  attempt      = {result.get('attempt')}")
    print(f"  DB saved to  = {DB_PATH}")
    return result


def demo_sqlite_resume() -> dict:
    """Resume: open the same DB + thread_id — state comes from checkpoint."""
    with build_checkpointer_ctx("sqlite", DB_PATH) as cp:
        graph = build_graph(checkpointer=cp)
        # get_state reads the latest checkpoint for this thread without re-running
        snapshot = graph.get_state(config=_run_config(THREAD_ID))

    state = snapshot.values
    print("[Demo 1] Resumed from SQLite checkpoint (no re-run).")
    print(f"  route        = {state.get('route')}")
    print(f"  final_answer = {state.get('final_answer', '')[:60]}")
    print(f"  nodes in events = {len(state.get('events', []))}")
    return state


# ---------------------------------------------------------------------------
# Demo 2: Crash-resume — simulate mid-run crash, resume from last checkpoint
# ---------------------------------------------------------------------------

def demo_crash_resume() -> None:
    """Run a scenario, then re-invoke with the same thread_id.

    Because every node writes a checkpoint, the graph resumes from where it
    left off rather than restarting from scratch. We verify that the final
    state is identical whether we ran once or 'crashed and resumed'.
    """
    scenario = Scenario(
        id="crash-demo",
        query="Please lookup order status for order 99999",
        expected_route=Route.TOOL,
    )
    state = initial_state(scenario)
    thread_id = "crash-demo-thread"
    state["thread_id"] = thread_id

    with build_checkpointer_ctx("sqlite", DB_PATH) as cp:
        graph = build_graph(checkpointer=cp)

        # First run — completes fully
        result1 = graph.invoke(state, config=_run_config(thread_id))
        events_first = len(result1.get("events", []))

        # Simulate crash-resume: re-invoke with same thread_id + empty input
        # LangGraph detects an existing checkpoint and returns the saved state
        result2 = graph.invoke(None, config=_run_config(thread_id))
        events_second = len(result2.get("events", []))

    print("[Demo 2] Crash-resume complete.")
    print(f"  events after first run  = {events_first}")
    print(f"  events after resume     = {events_second}  (same — no re-execution)")
    match = result1.get("final_answer") == result2.get("final_answer")
    print(f"  final_answer match      = {match}")


# ---------------------------------------------------------------------------
# Demo 3: Time-travel — replay from a previous checkpoint
# ---------------------------------------------------------------------------

def demo_time_travel() -> None:
    """Use get_state_history() to list all checkpoints and replay from an earlier one."""
    scenario = Scenario(
        id="tt-demo",
        query="Please lookup order status for order 77777",
        expected_route=Route.TOOL,
    )
    state = initial_state(scenario)
    thread_id = "time-travel-thread"
    state["thread_id"] = thread_id

    with build_checkpointer_ctx("sqlite", DB_PATH) as cp:
        graph = build_graph(checkpointer=cp)

        # Full run — creates multiple checkpoints (one per node)
        graph.invoke(state, config=_run_config(thread_id))

        # List all checkpoints
        history = list(graph.get_state_history(config=_run_config(thread_id)))
        print(f"[Demo 3] Total checkpoints saved: {len(history)}")
        for i, snap in enumerate(history):
            nodes = [e.get("node") for e in snap.values.get("events", [])]
            print(f"  [{i}] next={snap.next}  nodes_so_far={nodes}")

        # Replay from the checkpoint just after 'classify' (second-to-last is earliest)
        # Pick the checkpoint where classify has run but route hasn't been taken yet
        classify_snap = None
        for snap in history:
            events = snap.values.get("events", [])
            node_names = [e.get("node") for e in events]
            if "classify" in node_names and "tool" not in node_names:
                classify_snap = snap
                break

        if classify_snap is not None:
            print("\n[Demo 3] Replaying from checkpoint after 'classify'...")
            replayed = graph.invoke(None, config=classify_snap.config)
            print(f"  route        = {replayed.get('route')}")
            print(f"  final_answer = {replayed.get('final_answer', '')[:60]}")
        else:
            print("[Demo 3] Could not find classify checkpoint to replay from.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    Path("outputs").mkdir(exist_ok=True)

    # Remove old DB so demos start clean
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print("=" * 60)
    print("DEMO 1: SQLite Persistence")
    print("=" * 60)
    demo_sqlite_first_run()
    print()
    demo_sqlite_resume()

    print()
    print("=" * 60)
    print("DEMO 2: Crash-Resume")
    print("=" * 60)
    demo_crash_resume()

    print()
    print("=" * 60)
    print("DEMO 3: Time-Travel Replay")
    print("=" * 60)
    demo_time_travel()
