"""LLM-based classifier using OpenAI API.

Replaces keyword heuristics with semantic understanding so that:
- Typos  : "delte my account" → risky  (keyword misses, LLM understands)
- Synonyms: "reverse the charge" → risky (not in keyword list, LLM knows)
- Slang  : "my app keeps crashing" → error (not a keyword, LLM understands)

Usage:
    Set OPENAI_API_KEY in .env and use_llm_classifier: true in configs/lab.yaml.
    Without a key the module gracefully falls back to keyword classification.
"""

from __future__ import annotations

import json
import logging
import os

from .state import Route

log = logging.getLogger("agent_lab.llm_classifier")

_SYSTEM_PROMPT = """\
You are a query router for a customer support agent.
Classify the user query into exactly one of these routes:

- simple      : General question, FAQ, how-to. No data lookup or risky action needed.
- tool        : Requires fetching data (order status, account info, balance lookup, search).
- missing_info: Query is too vague or short to act on — clarification is needed.
- risky       : Involves a destructive, irreversible, or financial action that requires \
human approval. This includes: refund (any query mentioning refund — even status checks — \
because refunds involve financial approval), delete, cancel orders/accounts, \
transfer money, send bulk/mass emails or notifications. \
Password reset and account lookup are NOT risky — they are simple or tool routes.
- error       : The user describes a technical failure, crash, timeout, or system error \
that may need retry logic.

Rules:
1. If the query contains a typo but the intent is clear, classify by INTENT not spelling.
2. If the query uses synonyms (reverse charge = refund, remove = delete, crashing = error), \
classify by MEANING.
3. Respond ONLY with a JSON object: {"route": "<route>", "reason": "<one sentence>"}
4. Never add extra text outside the JSON.
"""


def classify_with_llm(query: str, model: str = "gpt-4o-mini") -> tuple[str, str]:
    """Call OpenAI to classify the query semantically.

    Returns (route_value, reason). Falls back to keyword classification on any error.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "your-openai-api-key-here":
        log.debug("llm_classifier: no API key — skipping LLM call")
        return _keyword_fallback(query)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=80,
        )
        raw = response.choices[0].message.content or ""
        parsed = json.loads(raw)
        route = parsed.get("route", "simple")
        reason = parsed.get("reason", "")

        # Validate route value
        valid = {r.value for r in Route}
        if route not in valid:
            log.warning("llm_classifier: invalid route=%r, falling back", route)
            return _keyword_fallback(query)

        log.info("llm_classifier: route=%s reason='%s'", route, reason)
        return route, reason

    except Exception as exc:
        log.warning("llm_classifier: error %s — falling back to keywords", exc)
        return _keyword_fallback(query)


def _keyword_fallback(query: str) -> tuple[str, str]:
    """Keyword-based fallback — same logic as classify_node."""
    q = query.lower()
    words = q.split()
    clean = [w.strip("?!.,;:") for w in words]

    if any(kw in q for kw in ("refund", "delete", "send", "cancel", "transfer")):
        return Route.RISKY.value, "keyword match: risky action"
    if any(kw in q for kw in ("timeout", "fail", "failure", "error", "cannot recover")):
        return Route.ERROR.value, "keyword match: error/failure"
    if any(kw in q for kw in ("status", "order", "lookup", "search", "find", "check")):
        return Route.TOOL.value, "keyword match: data lookup"
    if len(clean) < 5 and any(w in clean for w in ("it", "this", "that", "them")):
        return Route.MISSING_INFO.value, "short vague query"
    return Route.SIMPLE.value, "keyword fallback: simple"
