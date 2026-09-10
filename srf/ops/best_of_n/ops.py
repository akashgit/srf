"""Best-of-N domain operations."""

from __future__ import annotations

from typing import Any

import structlog

from srf.ops.common.paths import write_declared
from srf.ops.common.prompts import format_instructions, format_program_context, format_task_header

logger = structlog.get_logger()


def build_candidate_prompt(ctx: Any) -> None:
    """Build prompt for generating a candidate solution.

    Each parallel branch declares its own prompt file, so the N candidates
    sampled concurrently do not overwrite one another's prompt.
    """
    task = ctx.task
    parts = [
        format_task_header(task),
        format_program_context(task.get("initial_code", ""), label="Initial Code"),
        format_instructions("best_of_n"),
    ]
    write_declared(ctx, "candidate_prompt.md", "\n\n".join(parts), suffix=".md")


def select_best_candidate(ctx: Any) -> None:
    """Select the best candidate from N evaluations."""
    best_score = -float("inf")
    best_code = ""

    n = int(ctx.knobs.get("n_candidates", 5))
    for i in range(n):
        result = ctx.read_json(f"eval_result_{i}.json")
        code = ctx.read_text(f"candidate_{i}.py")
        if result and result.get("score", 0.0) > best_score and not result.get("error"):
            best_score = result["score"]
            best_code = code

    if best_code:
        ctx.write_text("best_solution.py", best_code)
    safe_score = best_score if best_score != -float("inf") else 0.0
    ctx.write_json("best_of_n_result.json", {"best_score": safe_score, "n": n})
    logger.info("best_of_n.selected", best_score=best_score)
