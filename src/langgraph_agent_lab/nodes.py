"""Node implementations for the LangGraph workflow.

Each function receives the current state and returns a partial state update dict.
Nodes never mutate the input state in place.
"""

from __future__ import annotations

import logging
import re

from .state import AgentState, ApprovalDecision, Route, make_event

log = logging.getLogger("agent_lab.nodes")

# ---------------------------------------------------------------------------
# PII patterns for intake normalization
# ---------------------------------------------------------------------------
_PII_PATTERNS = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
]


def _redact_pii(text: str) -> tuple[str, list[str]]:
    """Return (redacted_text, list_of_pii_types_found)."""
    found: list[str] = []
    for pattern, placeholder in _PII_PATTERNS:
        if pattern.search(text):
            found.append(placeholder)
            text = pattern.sub(placeholder, text)
    return text, found


def intake_node(state: AgentState) -> dict:
    """Normalize raw query: strip whitespace, redact PII, extract metadata."""
    raw_query = state.get("query", "")
    query = raw_query.strip()
    query, pii_found = _redact_pii(query)
    word_count = len(query.split())
    metadata: dict = {"word_count": word_count}
    if pii_found:
        log.warning("intake: PII redacted %s from query", pii_found)
        metadata["pii_redacted"] = pii_found
    log.debug("intake: query='%s' words=%d", query[:60], word_count)
    return {
        "query": query,
        "messages": [f"intake: normalized query ({word_count} words)"],
        "events": [make_event("intake", "completed", "query normalized", **metadata)],
    }


def classify_node(state: AgentState) -> dict:
    """Classify the query into one of five routes using keyword heuristics.

    Route priority (highest → lowest):
      risky > error > tool > missing_info > simple
    """
    query = state.get("query", "").lower()
    words = query.split()
    clean_words = [w.strip("?!.,;:") for w in words]

    route = Route.SIMPLE
    risk_level = "low"

    # Risky: destructive or external side-effects requiring approval
    if any(kw in query for kw in ("refund", "delete", "send", "cancel", "transfer")):
        route = Route.RISKY
        risk_level = "high"
    # Error: known failure keywords that should trigger retry loop
    elif any(kw in query for kw in ("timeout", "fail", "failure", "error", "cannot recover")):
        route = Route.ERROR
    # Tool: requires data lookup from external system
    elif any(kw in query for kw in ("status", "order", "lookup", "search", "find", "check")):
        route = Route.TOOL
    # Missing info: query is too short or uses vague pronouns without context
    elif len(clean_words) < 5 and any(w in clean_words for w in ("it", "this", "that", "them")):
        route = Route.MISSING_INFO

    log.info("classify: route=%s risk=%s", route.value, risk_level)
    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route.value} risk={risk_level}")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask a specific clarification question based on what is missing in the query."""
    query = state.get("query", "")
    # Generate a targeted question based on vague query content
    if any(w in query.lower() for w in ("it", "this", "that", "them")):
        question = (
            f"Your request '{query}' is unclear. "
            "Could you provide the order ID, customer ID, or describe what you need help with?"
        )
    else:
        question = "Could you provide more context? For example, an order ID or description."
    return {
        "pending_question": question,
        "final_answer": question,
        "events": [make_event("clarify", "completed", "clarification question sent")],
    }


def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call.

    Idempotent: same scenario + attempt produces the same result class.
    Simulates transient failure for error-route scenarios until attempt >= 2.
    """
    attempt = int(state.get("attempt", 0))
    scenario_id = state.get("scenario_id", "unknown")
    route = state.get("route", "")

    if route == Route.ERROR.value and attempt < 2:
        result = f"ERROR: transient failure attempt={attempt} scenario={scenario_id}"
        event_msg = f"tool failed (transient) attempt={attempt}"
        log.warning("tool: transient failure attempt=%d scenario=%s", attempt, scenario_id)
    else:
        query = state.get("query", "")
        result = f"RESULT: mock-tool-result for scenario={scenario_id} query='{query[:40]}'"
        event_msg = f"tool succeeded attempt={attempt}"
        log.debug("tool: success attempt=%d scenario=%s", attempt, scenario_id)

    return {
        "tool_results": [result],
        "messages": [f"tool: {event_msg}"],
        "events": [make_event("tool", "completed", event_msg, attempt=attempt)],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action with evidence and risk justification for approval."""
    query = state.get("query", "")
    risk_level = state.get("risk_level", "high")
    proposed = (
        f"Proposed action for query: '{query[:60]}' — "
        f"risk_level={risk_level}. Requires human approval before execution."
    )
    return {
        "proposed_action": proposed,
        "messages": [f"risky_action: approval required for '{query[:40]}'"],
        "events": [
            make_event("risky_action", "pending_approval", "proposed action prepared",
                       risk_level=risk_level)
        ],
    }


def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.

    Set LANGGRAPH_INTERRUPT=true to use real interrupt() for HITL demos.
    Default uses mock decision so tests and CI run offline.
    """
    import os

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        value = interrupt({
            "proposed_action": state.get("proposed_action"),
            "risk_level": state.get("risk_level"),
        })
        if isinstance(value, dict):
            decision = ApprovalDecision(**value)
        else:
            decision = ApprovalDecision(approved=bool(value))
    else:
        decision = ApprovalDecision(approved=True, comment="mock approval for lab")

    return {
        "approval": decision.model_dump(),
        "messages": [f"approval: approved={decision.approved} by {decision.reviewer}"],
        "events": [make_event(
            "approval", "completed",
            f"approved={decision.approved}",
            reviewer=decision.reviewer,
            comment=decision.comment,
        )],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Increment retry counter and record the failure.

    Bounded by max_attempts — route_after_retry checks the counter and
    redirects to dead_letter when the limit is reached.
    """
    attempt = int(state.get("attempt", 0)) + 1
    max_attempts = int(state.get("max_attempts", 3))
    error_msg = f"transient failure attempt={attempt}/{max_attempts}"
    log.warning("retry: attempt=%d/%d scenario=%s", attempt, max_attempts, state.get("scenario_id"))
    return {
        "attempt": attempt,
        "errors": [error_msg],
        "messages": [f"retry: {error_msg}"],
        "events": [make_event(
            "retry", "completed",
            "retry attempt recorded",
            attempt=attempt,
            max_attempts=max_attempts,
        )],
    }


def answer_node(state: AgentState) -> dict:
    """Produce a grounded final response from tool results and approval context."""
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")

    if tool_results:
        latest = tool_results[-1]
        answer = f"Based on the tool result: {latest}"
        if approval:
            answer += f" | Approved by: {approval.get('reviewer', 'unknown')}"
    else:
        answer = "Your request has been processed successfully."

    return {
        "final_answer": answer,
        "messages": ["answer: generated final response"],
        "events": [make_event("answer", "completed", "final answer generated")],
    }


def evaluate_node(state: AgentState) -> dict:
    """Check latest tool result — the 'done?' gate that drives the retry loop.

    Returns evaluation_result='needs_retry' if tool failed, 'success' otherwise.
    route_after_evaluate reads this field to decide next node.
    """
    tool_results = state.get("tool_results", [])
    latest = tool_results[-1] if tool_results else ""

    if "ERROR" in latest:
        result = "needs_retry"
        msg = "tool result indicates failure, retry needed"
    else:
        result = "success"
        msg = "tool result satisfactory"

    return {
        "evaluation_result": result,
        "events": [make_event("evaluate", "completed", msg, evaluation_result=result)],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Log unresolvable failures after max retries are exhausted.

    Third layer of error strategy: retry -> (bounded) -> dead_letter.
    """
    attempt = int(state.get("attempt", 0))
    max_attempts = int(state.get("max_attempts", 3))
    scenario_id = state.get("scenario_id", "unknown")
    message = (
        f"Request could not be completed after {attempt}/{max_attempts} attempts "
        f"(scenario={scenario_id}). Logged for manual review."
    )
    log.error("dead_letter: exhausted %d/%d scenario=%s", attempt, max_attempts, scenario_id)
    return {
        "final_answer": message,
        "messages": [f"dead_letter: escalated after {attempt} attempts"],
        "events": [make_event(
            "dead_letter", "escalated",
            "max retries exceeded",
            attempt=attempt,
            max_attempts=max_attempts,
            scenario_id=scenario_id,
        )],
    }


def finalize_node(state: AgentState) -> dict:
    """Finalize the run and emit a final audit event."""
    route = state.get("route", "unknown")
    answer = state.get("final_answer") or state.get("pending_question") or "no output"
    return {
        "events": [
            make_event("finalize", "completed", "workflow finished",
                       route=route, answer_preview=answer[:60])
        ],
    }
