"""EvoX Meta domain operations — meta-learned evolution."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from srf.ops.common.prompts import format_program_context, format_task_header
from srf.ops.common.reflection import analyze_stagnation
from srf.ops.common.selection import select_parent

logger = structlog.get_logger()


def sample_with_strategy(ctx: Any) -> None:
    """Sample parent using current meta-learned strategy."""
    population = ctx.read_json("population.json") or {}
    state = ctx.read_json("evox_state.json") or {"eval_count": 0, "best_score": 0.0}

    if not population:
        ctx.write_json("selected_parent.json", {
            "id": "seed", "code": ctx.task.get("initial_code", ""), "score": 0.0,
        })
        return

    strategy = state.get("current_strategy", ctx.knobs.get("parent_selection", "best"))
    individuals = list(population.values())
    parent = select_parent(individuals, strategy=strategy)
    ctx.write_json("selected_parent.json", parent)


def build_evox_prompt(ctx: Any) -> None:
    task = ctx.task
    parent = ctx.read_json("selected_parent.json") or {}
    state = ctx.read_json("evox_state.json") or {}

    parts = [
        format_task_header(task),
        format_program_context(parent.get("code", ""), parent.get("score"), "Parent Solution"),
    ]

    current_strategy = state.get("current_strategy_description", "")
    if current_strategy:
        parts.append(f"## Current Meta-Strategy\n{current_strategy}")

    parts.append(
        "## Instructions\nApply the current evolution strategy to produce an improved solution. "
        "Output a single fenced code block."
    )
    ctx.write_text("evox_prompt.md", "\n\n".join(parts))


def build_meta_evolution_prompt(ctx: Any) -> None:
    """Build prompt for evolving the search strategy itself."""
    task = ctx.task
    state = ctx.read_json("evox_state.json") or {}
    population = ctx.read_json("population.json") or {}

    scores = [p.get("score", 0.0) for p in population.values()]
    pop_desc = f"Population size: {len(population)}, Score range: [{min(scores):.4f}, {max(scores):.4f}]" if scores else "Empty population"

    parts = [
        format_task_header(task),
        f"## Population Descriptor φ(D_t)\n{pop_desc}",
        f"## Current Strategy\n{state.get('current_strategy_description', 'Default: select best, mutate')}",
        f"## History\nEvaluations: {state.get('eval_count', 0)}, Best: {state.get('best_score', 0.0):.4f}",
        "## Instructions\nDesign a new mutation strategy. Describe:\n"
        "1. How to select parents\n2. What mutations to apply\n3. When to explore vs exploit\n"
        "Be specific and actionable.",
    ]
    ctx.write_text("meta_prompt.md", "\n\n".join(parts))


def update_evox_archive(ctx: Any) -> None:
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")
    parent = ctx.read_json("selected_parent.json") or {}
    population = ctx.read_json("population.json") or {}

    child_score = eval_result.get("score", 0.0)
    child_error = eval_result.get("error")
    child_id = hashlib.sha256(candidate_code.encode()).hexdigest()[:12]

    state = ctx.read_json("evox_state.json") or {"eval_count": 0, "best_score": 0.0, "history": []}
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

    stagnation = analyze_stagnation(state.get("history", []))
    if stagnation.get("stagnating"):
        state["needs_meta_evolution"] = True

    ctx.write_json("population.json", population)
    ctx.write_json("evox_state.json", state)


def apply_meta_strategy(ctx: Any) -> None:
    """Apply a newly evolved meta-strategy."""
    meta_output = ctx.read_text("meta_strategy.txt")
    state = ctx.read_json("evox_state.json") or {}
    state["current_strategy_description"] = meta_output[:500]
    state["needs_meta_evolution"] = False
    ctx.write_json("evox_state.json", state)
    logger.info("evox.meta_strategy_evolved")
