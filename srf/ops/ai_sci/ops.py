"""AI Scientist shared operations — ideation, writeup, review."""

from __future__ import annotations

from typing import Any

import structlog

from srf.ops.common.prompts import format_program_context, format_task_header

logger = structlog.get_logger()


def ideation(ctx: Any) -> None:
    """Generate research ideas for the task."""
    task = ctx.task
    parts = [
        format_task_header(task),
        "## Instructions\nGenerate 3-5 research ideas for improving the solution. "
        "For each idea, describe the approach, expected benefit, and risk. "
        "Output as a numbered list.",
    ]
    ctx.write_text("ideation_prompt.md", "\n\n".join(parts))


def writeup(ctx: Any) -> None:
    """Generate a structured report of findings."""
    task = ctx.task
    best_code = ctx.read_text("best_solution.py")
    state = ctx.read_json("ai_sci_state.json") or {}

    parts = [
        format_task_header(task),
        format_program_context(best_code, state.get("best_score"), "Best Solution"),
        "## Instructions\nWrite a structured report covering:\n"
        "1. Problem statement\n2. Approach taken\n3. Key findings\n"
        "4. Results and metrics\n5. Future directions",
    ]
    ctx.write_text("writeup_prompt.md", "\n\n".join(parts))


def review(ctx: Any) -> None:
    """Self-review the quality of the solution."""
    best_code = ctx.read_text("best_solution.py")
    state = ctx.read_json("ai_sci_state.json") or {}

    parts = [
        f"## Solution Review\nScore: {state.get('best_score', 0.0)}",
        format_program_context(best_code, label="Solution Under Review"),
        "## Instructions\nRate this solution on:\n"
        "1. Correctness (1-10)\n2. Efficiency (1-10)\n3. Novelty (1-10)\n"
        "4. Overall quality (1-10)\nProvide brief justification for each.",
    ]
    ctx.write_text("review_prompt.md", "\n\n".join(parts))


def stage_transition(ctx: Any) -> None:
    """Transition between AI Scientist V2 stages."""
    state = ctx.read_json("ai_sci_state.json") or {"current_stage": 0, "stages_completed": []}
    stage = state.get("current_stage", 0)
    state["stages_completed"] = state.get("stages_completed", [])
    state["stages_completed"].append(stage)
    state["current_stage"] = stage + 1
    ctx.write_json("ai_sci_state.json", state)
    logger.info("ai_sci.stage_transition", from_stage=stage, to_stage=stage + 1)
