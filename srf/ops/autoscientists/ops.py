"""AutoScientists domain operations — multi-agent team."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from srf.ops.common.paths import write_declared
from srf.ops.common.prompts import format_program_context, format_task_header

logger = structlog.get_logger()


def build_scientist_prompt(ctx: Any) -> None:
    """Build prompt for individual scientist agents.

    Each parallel branch declares its own prompt file, so the scientists run
    concurrently without overwriting one another's prompt.
    """
    task = ctx.task
    parts = [
        format_task_header(task),
        format_program_context(task.get("initial_code", ""), label="Initial Code"),
        "## Instructions\nYou are one of multiple scientist agents working on this problem. "
        "Take a unique approach — don't follow the obvious path. "
        "Output a single fenced code block with a complete solution.",
    ]
    write_declared(ctx, "scientist_prompt.md", "\n\n".join(parts), suffix=".md")


def build_merge_prompt(ctx: Any) -> None:
    """Build merge prompt from multiple scientist solutions."""
    task = ctx.task
    n_scientists = int(ctx.knobs.get("n_scientists", 3))
    parts = [format_task_header(task), "## Scientist Solutions"]

    for i in range(n_scientists):
        code = ctx.read_text(f"scientist_{i}.py")
        result = ctx.read_json(f"scientist_result_{i}.json")
        score = result.get("score", 0.0) if result else 0.0
        if code:
            parts.append(format_program_context(code, score, f"Scientist {i+1}"))

    parts.append(
        "## Instructions\nYou are a merge agent. Read all scientist solutions above. "
        "Combine the best insights from each into a single superior solution. "
        "Output a single fenced code block."
    )
    ctx.write_text("merge_prompt.md", "\n\n".join(parts))


def update_autoscientists(ctx: Any) -> None:
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")

    child_score = eval_result.get("score", 0.0)
    child_error = eval_result.get("error")

    state = ctx.read_json("autoscientists_state.json") or {"eval_count": 0, "best_score": 0.0}
    state["eval_count"] = state.get("eval_count", 0) + 1

    if not child_error and child_score > state.get("best_score", 0.0):
        state["best_score"] = child_score
        ctx.write_text("best_solution.py", candidate_code)

    ctx.write_json("autoscientists_state.json", state)
