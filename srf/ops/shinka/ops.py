"""ShinkaEvolve domain operations — reflection + evolution."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from srf.ops.common.prompts import format_program_context, format_task_header
from srf.ops.common.reflection import analyze_stagnation, build_reflection_prompt
from srf.ops.common.selection import select_parent

logger = structlog.get_logger()


def sample_and_reflect(ctx: Any) -> None:
    """Sample parent and optionally trigger reflection."""
    population = ctx.read_json("population.json") or {}
    state = ctx.read_json("shinka_state.json") or {"eval_count": 0, "best_score": 0.0, "history": []}
    reflect_interval = int(ctx.knobs.get("reflect_interval", 5))

    if not population:
        ctx.write_json("selected_parent.json", {
            "id": "seed", "code": ctx.task.get("initial_code", ""), "score": 0.0,
        })
        ctx.write_text("reflection.md", "")
        return

    individuals = list(population.values())
    strategy = ctx.knobs.get("parent_selection", "best")
    parent = select_parent(individuals, strategy=strategy)
    ctx.write_json("selected_parent.json", parent)

    history = state.get("history", [])
    if len(history) > 0 and len(history) % reflect_interval == 0:
        reflection = build_reflection_prompt(ctx.task, history)
        ctx.write_text("reflection.md", reflection)
    else:
        ctx.write_text("reflection.md", "")


def build_shinka_prompt(ctx: Any) -> None:
    task = ctx.task
    parent = ctx.read_json("selected_parent.json") or {}
    reflection = ctx.read_text("reflection.md")

    parts = [
        format_task_header(task),
        format_program_context(parent.get("code", ""), parent.get("score"), "Parent Solution"),
    ]
    if reflection:
        parts.append(f"## Reflection Insights\n{reflection}")
    parts.append(
        "## Instructions\nEvolve the parent solution. Use the reflection insights if available. "
        "Output a single fenced code block."
    )
    ctx.write_text("shinka_prompt.md", "\n\n".join(parts))


def update_shinka_archive(ctx: Any) -> None:
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")
    parent = ctx.read_json("selected_parent.json") or {}
    population = ctx.read_json("population.json") or {}

    child_score = eval_result.get("score", 0.0)
    child_error = eval_result.get("error")
    child_id = hashlib.sha256(candidate_code.encode()).hexdigest()[:12]
    parent_score = parent.get("score", 0.0)

    state = ctx.read_json("shinka_state.json") or {"eval_count": 0, "best_score": 0.0, "history": []}
    state["eval_count"] = state.get("eval_count", 0) + 1

    improved = not child_error and child_score > parent_score
    state.setdefault("history", []).append({
        "score": child_score, "action": "evolve", "improved": improved,
    })

    if not child_error and child_score > parent_score * 0.95:
        population[child_id] = {
            "id": child_id, "code": candidate_code, "score": child_score,
            "metrics": eval_result.get("metrics", {}),
        }
        if child_score > state.get("best_score", 0.0):
            state["best_score"] = child_score
            state["best_id"] = child_id
            ctx.write_text("best_solution.py", candidate_code)

    ctx.write_json("population.json", population)
    ctx.write_json("shinka_state.json", state)


def init_shinka_state(ctx: Any) -> None:
    initial_code = ctx.task.get("initial_code", "")
    seed_id = hashlib.sha256(initial_code.encode()).hexdigest()[:12]
    ctx.write_json("population.json", {seed_id: {"id": seed_id, "code": initial_code, "score": 0.0}})
    ctx.write_json("shinka_state.json", {"eval_count": 0, "best_score": 0.0, "history": []})
    ctx.write_text("best_solution.py", initial_code)
