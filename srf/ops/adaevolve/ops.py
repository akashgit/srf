"""AdaEvolve domain operations — adaptive evolution with 3-level hierarchy."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from srf.ops.common.prompts import format_program_context, format_task_header
from srf.ops.common.reflection import analyze_stagnation
from srf.ops.common.selection import select_parent

logger = structlog.get_logger()


def adaptive_sample(ctx: Any) -> None:
    """Sample parent with adaptive exploration intensity."""
    population = ctx.read_json("population.json") or {}
    state = ctx.read_json("adaevolve_state.json") or {"eval_count": 0, "best_score": 0.0, "history": []}

    if not population:
        ctx.write_json("selected_parent.json", {
            "id": "seed", "code": ctx.task.get("initial_code", ""), "score": 0.0,
        })
        return

    stagnation = analyze_stagnation(state.get("history", []))
    strategy = "uniform" if stagnation.get("stagnating") else ctx.knobs.get("parent_selection", "best")
    individuals = list(population.values())
    parent = select_parent(individuals, strategy=strategy)
    ctx.write_json("selected_parent.json", parent)
    ctx.write_json("ada_stagnation.json", stagnation)


def build_ada_prompt(ctx: Any) -> None:
    task = ctx.task
    parent = ctx.read_json("selected_parent.json") or {}
    stagnation = ctx.read_json("ada_stagnation.json") or {}

    parts = [
        format_task_header(task),
        format_program_context(parent.get("code", ""), parent.get("score"), "Parent Solution"),
    ]
    if stagnation.get("stagnating"):
        parts.append(
            "## Meta-Strategy Note\nThe search is stagnating. "
            "Try a fundamentally different approach rather than incremental changes."
        )
    parts.append(
        "## Instructions\nProduce an improved solution. "
        "Output a single fenced code block."
    )
    ctx.write_text("ada_prompt.md", "\n\n".join(parts))


def update_ada_archive(ctx: Any) -> None:
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")
    parent = ctx.read_json("selected_parent.json") or {}
    population = ctx.read_json("population.json") or {}

    child_score = eval_result.get("score", 0.0)
    child_error = eval_result.get("error")
    child_id = hashlib.sha256(candidate_code.encode()).hexdigest()[:12]

    state = ctx.read_json("adaevolve_state.json") or {"eval_count": 0, "best_score": 0.0, "history": []}
    state["eval_count"] = state.get("eval_count", 0) + 1

    improved = not child_error and child_score > parent.get("score", 0.0)
    state.setdefault("history", []).append({"score": child_score, "improved": improved})

    if not child_error and child_score > parent.get("score", 0.0) * 0.95:
        population[child_id] = {
            "id": child_id, "code": candidate_code, "score": child_score,
            "metrics": eval_result.get("metrics", {}),
        }
        if child_score > state.get("best_score", 0.0):
            state["best_score"] = child_score
            state["best_id"] = child_id
            ctx.write_text("best_solution.py", candidate_code)

    ctx.write_json("population.json", population)
    ctx.write_json("adaevolve_state.json", state)


def meta_strategy_gate_fn(ctx: Any) -> None:
    """Write meta-strategy decision based on stagnation."""
    state = ctx.read_json("adaevolve_state.json") or {}
    stagnation = analyze_stagnation(state.get("history", []))
    decision = "META" if stagnation.get("stagnating") else "NORMAL"
    ctx.write_text("meta_decision.txt", decision)
