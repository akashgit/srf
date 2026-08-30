"""Karpathy mode operations — Claude Code agent with tool access."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from srf.ops.common.prompts import format_eval_feedback, format_program_context, format_task_header

logger = structlog.get_logger()


def build_agent_prompt(ctx: Any) -> None:
    """Build prompt for the agent with full context."""
    task = ctx.task
    best_code = ctx.read_text("best_solution.py")
    state = ctx.read_json("karpathy_state.json") or {}
    eval_result = ctx.read_json("eval_result.json")

    parts = [
        format_task_header(task),
        format_program_context(best_code, state.get("best_score"), "Current Best"),
    ]
    if eval_result:
        parts.append(format_eval_feedback(eval_result))
    parts.append(
        "## Instructions\nYou are an autonomous code optimization agent. "
        "Analyze the current solution and evaluation results, then produce an improved version. "
        "Think step by step about what could be improved. "
        "Output a single fenced code block with the complete solution."
    )
    ctx.write_text("agent_prompt.md", "\n\n".join(parts))


def update_karpathy_state(ctx: Any) -> None:
    """Update state after agent iteration."""
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")

    child_score = eval_result.get("score", 0.0)
    child_error = eval_result.get("error")

    state = ctx.read_json("karpathy_state.json") or {
        "eval_count": 0, "best_score": 0.0, "turns": 0,
    }
    state["eval_count"] = state.get("eval_count", 0) + 1
    state["turns"] = state.get("turns", 0) + 1

    if not child_error and child_score > state.get("best_score", 0.0):
        state["best_score"] = child_score
        ctx.write_text("best_solution.py", candidate_code)
        logger.info("karpathy.new_best", score=child_score)

    ctx.write_json("karpathy_state.json", state)


def init_karpathy_state(ctx: Any) -> None:
    ctx.write_json("karpathy_state.json", {"eval_count": 0, "best_score": 0.0, "turns": 0})
    ctx.write_text("best_solution.py", ctx.task.get("initial_code", ""))
