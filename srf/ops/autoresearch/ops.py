"""AutoResearch domain operations — research-driven optimization."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from srf.ops.common.prompts import format_program_context, format_task_header
from srf.ops.common.research import build_research_context, load_literature_context

logger = structlog.get_logger()


def research_phase(ctx: Any) -> None:
    """Build research prompt from task and literature context."""
    task = ctx.task
    literature = load_literature_context(ctx)
    research_context = build_research_context(task, literature)

    parts = [
        format_task_header(task),
        research_context,
        "## Instructions\nSynthesize relevant approaches from the research context. "
        "Identify 2-3 promising strategies for this optimization task. "
        "For each strategy, explain why it might work.",
    ]
    ctx.write_text("research_prompt.md", "\n\n".join(parts))


def build_optimization_prompt(ctx: Any) -> None:
    """Build optimization prompt informed by research."""
    task = ctx.task
    research = ctx.read_text("research_output.md")
    best_code = ctx.read_text("best_solution.py")
    state = ctx.read_json("autoresearch_state.json") or {}

    parts = [
        format_task_header(task),
        format_program_context(best_code, state.get("best_score"), "Current Best"),
    ]
    if research:
        parts.append(f"## Research Findings\n{research[:1500]}")
    parts.append(
        "## Instructions\nUsing the research findings, produce an improved solution. "
        "Output a single fenced code block."
    )
    ctx.write_text("optimize_prompt.md", "\n\n".join(parts))


def update_autoresearch(ctx: Any) -> None:
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")

    child_score = eval_result.get("score", 0.0)
    child_error = eval_result.get("error")

    state = ctx.read_json("autoresearch_state.json") or {"eval_count": 0, "best_score": 0.0}
    state["eval_count"] = state.get("eval_count", 0) + 1

    if not child_error and child_score > state.get("best_score", 0.0):
        state["best_score"] = child_score
        ctx.write_text("best_solution.py", candidate_code)

    ctx.write_json("autoresearch_state.json", state)
