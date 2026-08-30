"""SCS domain operations — archive sampling, prompt building, archive update."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from srf.ops.common.prompts import format_instructions, format_program_context, format_task_header
from srf.ops.common.selection import select_parent

logger = structlog.get_logger()


def sample_from_archive(ctx: Any) -> None:
    """Sample parent(s) from the population archive."""
    population = ctx.read_json("population.json") or {}
    strategy = ctx.knobs.get("parent_selection", "best")

    if not population:
        ctx.write_json("selected_parent.json", {
            "id": "seed", "code": ctx.task.get("initial_code", ""),
            "score": 0.0, "metrics": {},
        })
        return

    individuals = list(population.values())
    selected = select_parent(individuals, strategy=strategy)
    ctx.write_json("selected_parent.json", {
        "id": selected["id"], "code": selected["code"],
        "score": selected.get("score", 0.0), "metrics": selected.get("metrics", {}),
    })


def build_scs_prompt(ctx: Any) -> None:
    """Build prompt with archive context."""
    task = ctx.task
    parent = ctx.read_json("selected_parent.json") or {}
    population = ctx.read_json("population.json") or {}

    parts = [format_task_header(task)]

    top_programs = sorted(population.values(), key=lambda p: p.get("score", 0.0), reverse=True)[:3]
    for i, prog in enumerate(top_programs):
        parts.append(format_program_context(prog.get("code", ""), prog.get("score"), f"Archive Program {i+1}"))

    parts.append(format_program_context(parent.get("code", ""), parent.get("score"), "Selected Parent"))
    parts.append(format_instructions("scs"))

    ctx.write_text("scs_prompt.md", "\n\n".join(parts))


def update_archive(ctx: Any) -> None:
    """Evaluate and add candidate to archive if good enough."""
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")
    parent = ctx.read_json("selected_parent.json") or {}
    population = ctx.read_json("population.json") or {}

    child_score = eval_result.get("score", 0.0)
    child_error = eval_result.get("error")
    parent_score = parent.get("score", 0.0)

    child_id = hashlib.sha256(candidate_code.encode()).hexdigest()[:12]

    state = ctx.read_json("scs_state.json") or {
        "best_score": 0.0, "best_id": None, "eval_count": 0,
    }
    state["eval_count"] = state.get("eval_count", 0) + 1

    if not child_error and child_score > parent_score * 0.95:
        population[child_id] = {
            "id": child_id, "code": candidate_code, "score": child_score,
            "metrics": eval_result.get("metrics", {}),
            "generation": state["eval_count"], "parent_id": parent.get("id"),
        }
        if child_score > state.get("best_score", 0.0):
            state["best_score"] = child_score
            state["best_id"] = child_id
            ctx.write_text("best_solution.py", candidate_code)
            logger.info("scs.new_best", score=child_score, id=child_id)

    ctx.write_json("population.json", population)
    ctx.write_json("scs_state.json", state)


def init_scs_state(ctx: Any) -> None:
    """Initialize SCS state."""
    initial_code = ctx.task.get("initial_code", "")
    seed_id = hashlib.sha256(initial_code.encode()).hexdigest()[:12]
    population = {
        seed_id: {
            "id": seed_id, "code": initial_code, "score": 0.0,
            "metrics": {}, "generation": 0, "parent_id": None,
        }
    }
    ctx.write_json("population.json", population)
    ctx.write_json("scs_state.json", {"best_score": 0.0, "best_id": None, "eval_count": 0})
    ctx.write_text("best_solution.py", initial_code)
