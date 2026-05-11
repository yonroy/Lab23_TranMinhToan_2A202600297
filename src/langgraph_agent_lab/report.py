"""Report generation helper."""

from __future__ import annotations

from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a full lab report from metrics data."""

    # Build scenario results table
    rows = []
    for s in metrics.scenario_metrics:
        success_str = "YES" if s.success else "NO"
        rows.append(
            f"| {s.scenario_id} | {s.expected_route} | {s.actual_route or 'N/A'} "
            f"| {success_str} | {s.retry_count} | {s.interrupt_count} | {s.latency_ms} ms |"
        )
    scenario_table = "\n".join(rows)

    return f"""# Day 08 Lab Report

## 1. Team / student

- Name: Tran Minh Toan
- Repo/commit: Lab23_TranMinhToan_2A202600297
- Date: 2026-05-11

## 2. Architecture

The agent uses a LangGraph `StateGraph` with 11 nodes and conditional routing:

```
START -> intake -> classify -> route_after_classify
  simple       -> answer -> finalize -> END
  tool         -> tool -> evaluate -> route_after_evaluate
                   success  -> answer -> finalize -> END
                   needs_retry -> retry -> route_after_retry
                     attempt < max  -> tool (loop)
                     attempt >= max -> dead_letter -> finalize -> END
  missing_info -> clarify -> finalize -> END
  risky        -> risky_action -> approval -> route_after_approval
                   approved    -> tool -> evaluate -> ... (same as tool path)
                   not approved -> clarify -> finalize -> END
  error        -> retry -> route_after_retry -> tool -> evaluate -> ... (retry loop)
```

Key design decisions:
- `evaluate_node` is the "done?" gate — overwrites `evaluation_result` each cycle so `route_after_evaluate` always reads the latest value.
- Retry loop is bounded by `max_attempts`; exhausted requests escalate to `dead_letter_node`.
- `MemorySaver` checkpointer persists state per `thread_id` across node boundaries.

## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| `messages` | append (`add`) | human-readable trace of every node action |
| `tool_results` | append (`add`) | full history of tool outputs needed for evaluation |
| `errors` | append (`add`) | accumulate all transient failures for grading |
| `events` | append (`add`) | structured audit log for metrics and report |
| `route` | overwrite | current classification — only latest matters |
| `risk_level` | overwrite | current risk assessment |
| `evaluation_result` | overwrite | CRITICAL: retry loop gate reads latest value only |
| `attempt` | overwrite | monotonically incremented by retry node |
| `max_attempts` | overwrite | fixed per scenario, set in initial_state |
| `final_answer` | overwrite | last resolved answer |
| `pending_question` | overwrite | last clarification question |
| `proposed_action` | overwrite | current risky action awaiting approval |
| `approval` | overwrite | HITL decision for current action |

## 4. Scenario results

| Scenario | Expected route | Actual route | Success | Retries | Interrupts | Latency |
|---|---|---|:---:|---:|---:|---:|
{scenario_table}

**Summary:**
- Total scenarios: {metrics.total_scenarios}
- Success rate: {metrics.success_rate:.2%}
- Average nodes visited: {metrics.avg_nodes_visited:.2f}
- Average latency: {metrics.avg_latency_ms:.0f} ms
- Total retries: {metrics.total_retries}
- Total interrupts: {metrics.total_interrupts}

## 5. Failure analysis

**Failure mode 1 — Transient tool failure (retry loop):**
Scenarios tagged `error` trigger `route=error` which enters the retry loop immediately (via `retry` node, not `tool`). Each cycle: `retry_or_fallback_node` increments `attempt`, then `route_after_retry` checks `attempt >= max_attempts`. If not exhausted, routes back to `tool`. The `tool_node` simulates transient failure when `attempt < 2`, so after 2 retries it succeeds. If `max_attempts=1` (S07), the loop exhausts immediately and routes to `dead_letter_node`.

**Failure mode 2 — Risky action rejected:**
If `approval_node` returns `approved=False`, `route_after_approval` redirects to `clarify` instead of `tool`. The risky action is never executed. In CI/lab mode, mock approval always returns `approved=True`; in real HITL mode (`LANGGRAPH_INTERRUPT=true`), a human can reject.

**Failure mode 3 — Missing information:**
Queries with vague pronouns and fewer than 5 words classify as `missing_info`. The graph skips tool calls entirely and returns a targeted clarification question as `final_answer` / `pending_question`.

## 6. Persistence / recovery evidence

- `MemorySaver` checkpointer is passed to `build_graph()` via `build_checkpointer("memory")`.
- Each scenario run uses a unique `thread_id = "thread-{{scenario_id}}"`, so state is isolated per run.
- LangGraph stores a checkpoint after every node, enabling state inspection with `graph.get_state(config)`.
- For crash-resume, re-invoking with the same `thread_id` and a `MemorySaver` would resume from the last checkpoint (demonstrated in the extension phase with SQLite).

## 7. Extension work

Three extensions implemented in `src/langgraph_agent_lab/extension_demo.py`
(run with `python -m langgraph_agent_lab.extension_demo`):

**Extension A — SQLite persistence** (`langgraph-checkpoint-sqlite`):
- Added `build_checkpointer_ctx()` context manager in `persistence.py` supporting `memory` / `sqlite` / `postgres`
- SQLite saves one checkpoint per node to `outputs/checkpoints.db`
- Verified: state reloaded from DB with `graph.get_state()` matches original run exactly

**Extension B — Crash-resume** (same `thread_id`):
- After a completed run, re-invoking with `graph.invoke(None, config=same_thread_id)` returns the saved final state without re-executing any node
- Demo output: `events after resume = 6 (same — no re-execution)`, `final_answer match = True`

**Extension C — Time-travel replay** (`get_state_history()`):
- `graph.get_state_history()` returns **8 checkpoints** for a 6-node tool scenario (one per node + START/END)
- Replayed from the checkpoint after `classify` (before `tool`): graph re-ran from that point and produced identical final answer
- Demo output:
```
[Demo 3] Total checkpoints saved: 8
  [4] next=('tool',)  nodes_so_far=['intake', 'classify']
Replaying from checkpoint after 'classify'...
  route = tool  |  final_answer = Based on the tool result: RESULT: mock-tool-result ...
```

## 8. Improvement plan

1. **Replace keyword classifier with LLM-as-judge** (`classify_node`): use a structured prompt to classify intent more accurately, especially for edge cases not covered by keywords.
2. **Add real latency tracking per node** using LangGraph's event streaming (`astream_events`) instead of wall-clock timing around the full graph invoke.
3. **SQLite persistence** for crash-resume: use `langgraph-checkpoint-sqlite` so state survives process restarts, enabling true HITL with async approval.
4. **Structured tool results** (dict/Pydantic model) instead of raw strings so `evaluate_node` can do schema validation rather than string matching.
"""


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
