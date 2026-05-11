"""State schema for the Day 08 LangGraph lab.

Students should extend the schema only when needed. Keep state lean and serializable.
"""

from __future__ import annotations

from enum import StrEnum
from operator import add
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field, field_validator


class Route(StrEnum):
    SIMPLE = "simple"
    TOOL = "tool"
    MISSING_INFO = "missing_info"
    RISKY = "risky"
    ERROR = "error"
    DEAD_LETTER = "dead_letter"
    DONE = "done"


class LabEvent(BaseModel):
    """Append-only audit event for grading and debugging."""

    node: str
    event_type: str
    message: str
    latency_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    approved: bool = False
    reviewer: str = "mock-reviewer"
    comment: str = ""


class AgentState(TypedDict, total=False):
    """LangGraph state for the Day 08 agent workflow.

    Field strategy:
    - APPEND-ONLY (Annotated[list, add]): audit trail fields that must never lose history.
      LangGraph merges these with the `add` reducer across checkpoints.
      - messages: human-readable trace of each node's action
      - tool_results: raw output from every tool call (needed for retry evaluation)
      - errors: every transient failure recorded for grading and debugging
      - events: structured audit log used by metrics and report

    - OVERWRITE (no reducer): scalar fields that represent current state, not history.
      - route / risk_level: set by classify_node, consumed by routing functions
      - attempt: incremented by retry_or_fallback_node; read by route_after_retry
      - max_attempts: fixed per scenario, never mutated after initial_state
      - evaluation_result: overwritten by evaluate_node each cycle — CRITICAL for retry
        loop gate (route_after_evaluate reads the LATEST value, not accumulated history)
      - final_answer / pending_question: last answer or clarification, set by answer/clarify nodes
      - proposed_action: set by risky_action_node, consumed by approval_node
      - approval: set by approval_node, consumed by route_after_approval
    """

    # Identity / config (overwrite)
    thread_id: str
    scenario_id: str
    query: str
    max_attempts: int

    # Routing (overwrite — current classification only)
    route: str
    risk_level: str

    # Retry loop control (overwrite — must reflect latest value for gate logic)
    attempt: int
    evaluation_result: str | None

    # Output (overwrite — final resolved value)
    final_answer: str | None
    pending_question: str | None
    proposed_action: str | None
    approval: dict[str, Any] | None

    # Audit trail (append-only — never overwrite, always accumulate)
    messages: Annotated[list[str], add]
    tool_results: Annotated[list[str], add]
    errors: Annotated[list[str], add]
    events: Annotated[list[dict[str, Any]], add]


class Scenario(BaseModel):
    id: str
    query: str
    expected_route: Route
    requires_approval: bool = False
    should_retry: bool = False
    max_attempts: int = 3
    tags: list[str] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value


def initial_state(scenario: Scenario) -> AgentState:
    """Create a serializable initial state for one scenario."""
    return {
        "thread_id": f"thread-{scenario.id}",
        "scenario_id": scenario.id,
        "query": scenario.query,
        "route": "",
        "risk_level": "unknown",
        "attempt": 0,
        "max_attempts": scenario.max_attempts,
        "final_answer": None,
        "pending_question": None,
        "proposed_action": None,
        "approval": None,
        "evaluation_result": None,
        "messages": [],
        "tool_results": [],
        "errors": [],
        "events": [],
    }


def make_event(node: str, event_type: str, message: str, **metadata: Any) -> dict[str, Any]:  # noqa: ANN401
    """Create a normalized event payload."""
    return LabEvent(
        node=node, event_type=event_type, message=message, metadata=metadata
    ).model_dump()
