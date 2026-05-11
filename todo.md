# Lab 23 - LangGraph Agent Lab: TODO by Phase

## Phase 0 — Setup (làm trước tiên)

**Goal:** Cài đặt môi trường, xác nhận project chạy được trước khi code.

### Cài dependencies
- [ ] Tạo virtual environment: `python -m venv .venv`
- [ ] Activate: `.venv\Scripts\activate` (Windows) hoặc `source .venv/bin/activate` (Mac/Linux)
- [ ] Cài packages: `pip install -e '.[dev]'`
- [ ] (Extension SQLite) Cài thêm: `pip install -e '.[dev,sqlite]'`

### Cấu hình môi trường
- [ ] Copy file env: `cp .env.example .env`
- [ ] Giữ mặc định `CHECKPOINTER=memory` cho lab cơ bản
- [ ] (Optional) Đặt `LOG_LEVEL=DEBUG` để xem log chi tiết hơn

### Verify setup
- [ ] Chạy `make test` — phải pass (smoke tests chạy được với skeleton hiện tại)
- [ ] Chạy `make lint` — kiểm tra code style
- [ ] Chạy `make run-scenarios` một lần để xem output mẫu (có thể chưa đầy đủ ở bước này)
- [ ] Kiểm tra file `outputs/metrics.json` được tạo ra

---

## Graph Flow Reference

```
START -> intake -> classify -> route
  route simple       -> answer -> finalize -> END
  route tool         -> tool -> evaluate -> answer -> finalize -> END
  route missing_info -> clarify -> finalize -> END
  route risky        -> risky_action -> approval -> tool -> evaluate -> answer -> finalize -> END
  route error        -> retry -> tool -> evaluate -> retry -> ... -> dead_letter -> finalize -> END
```

---

## Phase 1 — State Schema (`state.py`)

**Goal:** Confirm which fields are append-only vs overwrite, keep state lean and serializable.

- [ ] Confirm `messages`, `tool_results`, `errors`, `events` use `Annotated[list, add]` (append-only) — already done
- [ ] Confirm `evaluation_result` is overwrite — used as retry loop gate (read by `route_after_evaluate`)
- [ ] Confirm `attempt` is overwrite — incremented by `retry_or_fallback_node`
- [ ] Confirm `route`, `risk_level`, `final_answer`, `pending_question`, `proposed_action`, `approval` are overwrite
- [ ] Verify `initial_state()` initializes all fields to safe defaults
- [ ] (Optional) Add new fields only if needed for extension tasks

---

## Phase 2 — Nodes (`nodes.py`)

**Goal:** Implement node logic — each node returns a partial state dict, never mutates input state.

### `intake_node`
- [ ] Strip and normalize the raw query
- [ ] Add basic PII check (e.g., detect email, phone patterns)
- [ ] Add metadata extraction (e.g., detect language, query length)

### `classify_node`
- [ ] Keep keyword heuristic as baseline (already works for lab scenarios)
- [ ] Improve routing policy to clearly cover all 5 routes: `simple`, `tool`, `missing_info`, `risky`, `error`
- [ ] Ensure `risk_level` is set correctly (`"high"` for risky, `"low"` otherwise)

### `ask_clarification_node`
- [ ] Generate a specific clarification question based on what is missing in state
- [ ] Set `pending_question` and `final_answer` with the question

### `tool_node`
- [ ] Implement idempotent tool execution (same input -> same result)
- [ ] Return structured tool result (not just a plain string)
- [ ] Simulate transient failure for `route=error` when `attempt < 2` (already done)

### `evaluate_node`
- [ ] Check latest tool result for `"ERROR"` -> return `"needs_retry"` (already done)
- [ ] Return `"success"` when tool result is valid
- [ ] (Optional) Replace string heuristic with LLM-as-judge or structured validation

### `retry_or_fallback_node`
- [ ] Increment `attempt` counter
- [ ] Append error to `errors` list
- [ ] (Optional) Add exponential backoff metadata to event

### `dead_letter_node`
- [ ] Set `final_answer` to a clear error message for manual review
- [ ] Emit event with `max_attempts` context
- [ ] (Optional) Persist to dead-letter queue or create support ticket

### `answer_node`
- [ ] Ground answer in `tool_results[-1]` when available
- [ ] Reference `approval` info when route is risky
- [ ] Return meaningful `final_answer`

### `approval_node`
- [ ] Mock approval returns `approved=True` for CI/tests (already done)
- [ ] (Optional) Implement reject/edit decisions
- [ ] (Optional) Add timeout escalation logic

---

## Phase 3 — Routing (`routing.py`)

**Goal:** Make route decisions explicit and safe. All routes must lead to termination.

### `route_after_classify`
- [ ] Map all 5 route values to correct next nodes (already done)
- [ ] Handle unknown/unexpected route safely (default to `"answer"` already set)
- [ ] Update tests for edge cases

### `route_after_retry`
- [ ] Return `"dead_letter"` when `attempt >= max_attempts` (already done)
- [ ] Return `"tool"` to continue retry loop (already done)

### `route_after_evaluate`
- [ ] Return `"retry"` when `evaluation_result == "needs_retry"` (already done)
- [ ] Return `"answer"` when result is satisfactory (already done)
- [ ] This function creates the retry loop — verify it is bounded by `max_attempts`

### `route_after_approval`
- [ ] Return `"tool"` when approved (already done)
- [ ] Return `"clarify"` when not approved (already done)
- [ ] (Optional) Add `"edit"` outcome support

---

## Phase 4 — Graph, Metrics, Report

**Goal:** Verify all paths terminate. Run scenarios. Write final report.

### `graph.py`
- [ ] Review all edges and confirm every path reaches `finalize -> END`
- [ ] Confirm retry loop is bounded: `retry -> route_after_retry -> dead_letter` when limit reached
- [ ] (Optional) Modify nodes/edges only with a clear documented reason

### `metrics.py`
- [ ] Verify `metric_from_state()` captures correct fields
- [ ] Verify `summarize_metrics()` computes `success_rate`, `avg_nodes_visited`, `total_retries`
- [ ] (Optional) Add `latency_ms` tracking per scenario
- [ ] (Optional) Add extra custom metrics

### `report.py`
- [ ] Replace `render_report_stub()` with a full report using `reports/lab_report_template.md`
- [ ] Include: architecture explanation, metrics table, failure analysis, improvement plan

### Run and validate
- [ ] Run `make test` — all tests pass
- [ ] Run `make run-scenarios` — writes `outputs/metrics.json`
- [ ] Run `make grade-local` — validates metrics
- [ ] Fill in `reports/lab_report.md`

---

## Phase 5 — Extension Tasks (pick at least 1)

**Goal:** Demonstrate advanced LangGraph features for higher grade band.

- [ ] **SQLite persistence**: set `checkpointer: sqlite` in `configs/lab.yaml`, verify state survives restart
- [ ] **Crash-resume**: use same `thread_id` to resume from checkpoint after simulated crash
- [ ] **Time-travel replay**: use `get_state_history()` to replay from a previous checkpoint
- [ ] **Real HITL**: set `LANGGRAPH_INTERRUPT=true`, build Streamlit approval UI
- [ ] **Parallel fan-out**: call two mock tools in parallel and merge their evidence
- [ ] **Graph diagram**: export graph diagram and include in report

---

## Submission Checklist

- [ ] `make test` passes
- [ ] `make run-scenarios` writes `outputs/metrics.json`
- [ ] `make grade-local` validates metrics
- [ ] `reports/lab_report.md` is completed
- [ ] Can explain one route and one failure mode in demo

---

## Grading Reference

| Category | Points |
|---|---:|
| Architecture and state schema | 20 |
| Graph behavior (6 routes, bounded retry, HITL, all terminate) | 25 |
| Persistence and recovery | 15 |
| Metrics and tests | 20 |
| Report and demo | 15 |
| Production hygiene | 5 |
| **Total** | **100** |

Grade bands: 90-100 (production quality + extension) / 75-89 (core works + report) / 60-74 (incomplete persistence/report) / <60 (does not run)
