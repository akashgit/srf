"""OpenEvolve domain operations — multi-island MAP-Elites."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from srf.ops.common.migration import ring_migrate, should_migrate
from srf.ops.common.prompts import format_program_context, format_task_header
from srf.ops.common.selection import select_parent

logger = structlog.get_logger()


def sample_parent_and_inspiration(ctx: Any) -> None:
    """Sample a parent and an inspiration from the island's population."""
    island_id = int(ctx.knobs.get("current_island", 0))
    populations = ctx.read_json("island_populations.json") or {}
    island_pop = populations.get(str(island_id), [])

    if not island_pop:
        initial_code = ctx.task.get("initial_code", "")
        ctx.write_json("selected_parent.json", {"id": "seed", "code": initial_code, "score": 0.0})
        ctx.write_json("inspiration.json", {"id": "seed", "code": initial_code, "score": 0.0})
        return

    strategy = ctx.knobs.get("parent_selection", "best")
    parent = select_parent(island_pop, strategy=strategy)
    inspiration = select_parent(island_pop, strategy="uniform") if len(island_pop) > 1 else parent

    ctx.write_json("selected_parent.json", parent)
    ctx.write_json("inspiration.json", inspiration)


def build_evolve_prompt(ctx: Any) -> None:
    task = ctx.task
    parent = ctx.read_json("selected_parent.json") or {}
    inspiration = ctx.read_json("inspiration.json") or {}

    parts = [
        format_task_header(task),
        format_program_context(parent.get("code", ""), parent.get("score"), "Parent Solution"),
    ]
    if inspiration.get("id") != parent.get("id"):
        parts.append(format_program_context(inspiration.get("code", ""), inspiration.get("score"), "Inspiration"))
    parts.append(
        "## Instructions\nMutate the parent solution to improve its score. "
        "Draw inspiration from the other solution if present. "
        "Output a single fenced code block."
    )
    ctx.write_text("evolve_prompt.md", "\n\n".join(parts))


def update_island(ctx: Any) -> None:
    """Update island population with evaluated candidate."""
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")
    parent = ctx.read_json("selected_parent.json") or {}

    child_score = eval_result.get("score", 0.0)
    child_error = eval_result.get("error")
    child_id = hashlib.sha256(candidate_code.encode()).hexdigest()[:12]

    island_id = str(int(ctx.knobs.get("current_island", 0)))
    populations = ctx.read_json("island_populations.json") or {}
    island_pop = populations.get(island_id, [])

    state = ctx.read_json("openevolve_state.json") or {"eval_count": 0, "best_score": 0.0, "generation": 0}
    state["eval_count"] = state.get("eval_count", 0) + 1
    state["generation"] = state.get("generation", 0) + 1

    if not child_error and child_score > parent.get("score", 0.0) * 0.95:
        island_pop.append({
            "id": child_id, "code": candidate_code, "score": child_score,
            "metrics": eval_result.get("metrics", {}),
        })
        if child_score > state.get("best_score", 0.0):
            state["best_score"] = child_score
            state["best_id"] = child_id
            ctx.write_text("best_solution.py", candidate_code)

    populations[island_id] = island_pop

    if should_migrate(state["generation"], interval=int(ctx.knobs.get("migration_interval", 10))):
        all_islands = [populations.get(str(i), []) for i in range(int(ctx.knobs.get("n_islands", 3)))]
        all_islands = ring_migrate(all_islands)
        for i, island in enumerate(all_islands):
            populations[str(i)] = island

    ctx.write_json("island_populations.json", populations)
    ctx.write_json("openevolve_state.json", state)


def init_openevolve_state(ctx: Any) -> None:
    n_islands = int(ctx.knobs.get("n_islands", 3))
    initial_code = ctx.task.get("initial_code", "")
    seed_id = hashlib.sha256(initial_code.encode()).hexdigest()[:12]
    populations = {}
    for i in range(n_islands):
        populations[str(i)] = [{"id": seed_id, "code": initial_code, "score": 0.0, "metrics": {}}]
    ctx.write_json("island_populations.json", populations)
    ctx.write_json("openevolve_state.json", {"eval_count": 0, "best_score": 0.0, "generation": 0})
    ctx.write_text("best_solution.py", initial_code)
