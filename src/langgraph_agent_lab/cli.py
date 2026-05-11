"""CLI for the lab."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Annotated

import typer
import yaml
from dotenv import load_dotenv

load_dotenv()  # load .env vào os.environ trước khi đọc LOG_LEVEL / OPENAI_API_KEY

from .graph import build_graph
from .metrics import MetricsReport, metric_from_state, summarize_metrics, write_metrics
from .persistence import build_checkpointer
from .report import write_report
from .scenarios import load_scenarios
from .state import initial_state

# Đọc LOG_LEVEL từ .env (mặc định INFO)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("agent_lab.cli")

app = typer.Typer(no_args_is_help=True)


@app.command("run-scenarios")
def run_scenarios(
    config: Annotated[Path, typer.Option("--config")],
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Run all grading scenarios and write metrics JSON."""
    cfg = yaml.safe_load(config.read_text(encoding="utf-8"))
    scenarios = load_scenarios(cfg["scenarios_path"])
    checkpointer_kind = cfg.get("checkpointer", "memory")
    log.info("Loaded %d scenarios | checkpointer=%s", len(scenarios), checkpointer_kind)

    checkpointer = build_checkpointer(checkpointer_kind, cfg.get("database_url"))
    graph = build_graph(checkpointer=checkpointer)
    metrics = []
    for scenario in scenarios:
        state = initial_state(scenario)
        run_config = {"configurable": {"thread_id": state["thread_id"]}}
        log.info("▶ [%s] query='%s'", scenario.id, scenario.query[:50])
        t0 = time.monotonic()
        final_state = graph.invoke(state, config=run_config)
        latency_ms = int((time.monotonic() - t0) * 1000)
        actual_route = final_state.get("route")
        expected = scenario.expected_route.value
        status = "✓" if actual_route == expected else "✗"
        log.info(
            "  %s route=%s (expected=%s) retries=%d latency=%dms",
            status, actual_route, expected,
            sum(1 for e in final_state.get("events", []) if e.get("node") == "retry"),
            latency_ms,
        )
        if actual_route != expected:
            log.warning("  MISMATCH: %s got=%s expected=%s", scenario.id, actual_route, expected)
        metrics.append(metric_from_state(
            final_state, scenario.expected_route.value, scenario.requires_approval, latency_ms
        ))

    report = summarize_metrics(metrics)
    log.info(
        "Summary: %d/%d passed (%.0f%%) | avg_nodes=%.1f | retries=%d",
        int(report.success_rate * report.total_scenarios),
        report.total_scenarios,
        report.success_rate * 100,
        report.avg_nodes_visited,
        report.total_retries,
    )
    write_metrics(report, output)
    if cfg.get("report_path"):
        write_report(report, cfg["report_path"])
    typer.echo(f"Wrote metrics to {output}")


@app.command("validate-metrics")
def validate_metrics(metrics: Annotated[Path, typer.Option("--metrics")]) -> None:
    """Validate metrics JSON schema for grading."""
    payload = json.loads(metrics.read_text(encoding="utf-8"))
    report = MetricsReport.model_validate(payload)
    if report.total_scenarios < 6:
        raise typer.BadParameter("Expected at least 6 scenarios")
    typer.echo(f"Metrics valid. success_rate={report.success_rate:.2%}")


if __name__ == "__main__":
    app()
