"""Routing functions for conditional edges.

Each function receives the current AgentState and returns the name of the next
node as a string. Return values must exactly match node names registered in graph.py.

Route decision hierarchy:
  classify  -> route_after_classify  (5 routes)
  evaluate  -> route_after_evaluate  (retry loop gate: success | needs_retry)
  retry     -> route_after_retry     (bounded: tool | dead_letter)
  approval  -> route_after_approval  (HITL gate: approved | rejected)
"""

from __future__ import annotations

from .state import AgentState, Route

# Explicit mapping: all Route enum values -> next node name.
# Unknown routes fall back to "answer" so the graph always terminates.
_CLASSIFY_MAP: dict[str, str] = {
    Route.SIMPLE.value: "answer",
    Route.TOOL.value: "tool",
    Route.MISSING_INFO.value: "clarify",
    Route.RISKY.value: "risky_action",
    Route.ERROR.value: "retry",
    Route.DEAD_LETTER.value: "dead_letter",
    Route.DONE.value: "finalize",
}


def route_after_classify(state: AgentState) -> str:
    """Map the classified route to the next graph node.

    Falls back to 'answer' for any unknown route value so the graph
    always terminates rather than raising a KeyError at runtime.
    """
    route = state.get("route", Route.SIMPLE.value)
    return _CLASSIFY_MAP.get(route, "answer")


def route_after_retry(state: AgentState) -> str:
    """Decide whether to retry the tool call or escalate to dead-letter.

    Retry is bounded by max_attempts. Once attempt >= max_attempts the
    request is dead-lettered for manual review.

    Graph edge: retry -> tool (continue loop) | dead_letter (exhausted)
    """
    attempt = int(state.get("attempt", 0))
    max_attempts = int(state.get("max_attempts", 3))
    if attempt >= max_attempts:
        return "dead_letter"
    return "tool"


def route_after_evaluate(state: AgentState) -> str:
    """Decide whether the tool result is satisfactory or needs a retry.

    This is the 'done?' check that enables the retry loop — a key LangGraph
    advantage over LCEL. The evaluate node overwrites evaluation_result each
    cycle so this function always reads the latest value.

    Graph edge: evaluate -> retry (needs_retry) | answer (success)
    """
    if state.get("evaluation_result") == "needs_retry":
        return "retry"
    return "answer"


def route_after_approval(state: AgentState) -> str:
    """Continue only if the HITL approval was granted.

    - approved=True  -> proceed to tool execution
    - approved=False -> redirect to clarify (ask reviewer for correction)
    - approval=None  -> treat as rejected (safe default)

    Graph edge: approval -> tool (approved) | clarify (rejected/missing)
    """
    approval = state.get("approval") or {}
    if approval.get("approved"):
        return "tool"
    return "clarify"
