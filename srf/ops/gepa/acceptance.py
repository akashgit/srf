"""Acceptance gate — accept_or_reject with strict/lenient/off modes."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog

from srf.ops.common.budget import record_eval
from srf.ops.common.tracing import log_candidate, log_evaluation
from srf.ops.gepa.state import load_state, save_state

logger = structlog.get_logger()


def accept_or_reject(ctx: Any) -> None:
    """Compare child score to parent. Update population/genealogy/histories.

    Reads: eval_result.json, candidate.py, selected_parent.json,
           population.json, genealogy.json, gepa_state.json
    Writes: population.json, genealogy.json, rejection_history.json,
            accepted_history.json, gepa_state.json, best_solution.py
    """
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")
    parent = ctx.read_json("selected_parent.json") or {}
    population = ctx.read_json("population.json") or {}
    genealogy = ctx.read_json("genealogy.json") or {"nodes": {}, "edges": []}
    state = load_state(ctx)
    rejections = ctx.read_json("rejection_history.json") or []
    accepted = ctx.read_json("accepted_history.json") or []

    acceptance_mode = ctx.knobs.get("acceptance_mode", "strict")
    child_score = eval_result.get("score", 0.0)
    child_metrics = eval_result.get("metrics", {})
    child_error = eval_result.get("error")
    parent_score = parent.get("score", 0.0)
    parent_id = parent.get("id", "seed")
    source = state.last_action

    child_id = hashlib.sha256(candidate_code.encode()).hexdigest()[:12]

    record_eval(ctx)

    log_evaluation(ctx, child_id, child_score, child_metrics)
    log_candidate(ctx, child_id, parent_id, source, hashlib.sha256(candidate_code.encode()).hexdigest()[:16])

    state.iteration = ctx.iteration
    state.eval_count += 1

    if child_error:
        _reject(
            ctx, state, rejections, child_id, child_score, parent_score,
            candidate_code, child_error, child_metrics,
        )
        save_state(ctx, state)
        ctx.write_json("rejection_history.json", rejections)
        return

    is_accepted = _check_acceptance(acceptance_mode, child_score, parent_score, state, source)

    if is_accepted:
        population[child_id] = {
            "id": child_id,
            "code": candidate_code,
            "score": child_score,
            "metrics": child_metrics,
            "generation": state.iteration,
            "parent_id": parent_id,
        }
        genealogy["nodes"][child_id] = {"generation": state.iteration}
        genealogy["edges"].append({"source": parent_id, "target": child_id})

        accepted.append({
            "id": child_id,
            "score": child_score,
            "parent_score": parent_score,
            "iteration": ctx.iteration,
        })

        state.total_accepted += 1
        state.population_size = len(population)

        if child_score > state.best_score:
            state.best_score = child_score
            state.best_id = child_id
            state.stagnation_counter = 0
            state.merge_due = False
            state.merge_attempts = 0
            ctx.write_text("best_solution.py", candidate_code)
            logger.info("acceptance.new_best", score=child_score, id=child_id)
        else:
            state.stagnation_counter += 1

        logger.info(
            "acceptance.accepted",
            child_id=child_id,
            child_score=child_score,
            parent_score=parent_score,
            mode=acceptance_mode,
        )
    else:
        _reject(
            ctx, state, rejections, child_id, child_score, parent_score,
            candidate_code, None, child_metrics,
        )

    ctx.write_json("population.json", population)
    ctx.write_json("genealogy.json", genealogy)
    ctx.write_json("rejection_history.json", rejections)
    ctx.write_json("accepted_history.json", accepted)
    save_state(ctx, state)


def _check_acceptance(mode: str, child_score: float, parent_score: float, state: Any, source: str = "mutate") -> bool:
    if mode == "off":
        return True
    if mode == "lenient":
        return child_score >= parent_score * 0.95
    # Strict mode: child > parent for mutate, child >= best_parent for merge
    if source == "merge":
        return child_score >= parent_score
    return child_score > parent_score


def _reject(
    ctx: Any,
    state: Any,
    rejections: list,
    child_id: str,
    child_score: float,
    parent_score: float,
    code: str,
    error: str | None,
    metrics: dict,
) -> None:
    rejections.append({
        "id": child_id,
        "score": child_score,
        "parent_score": parent_score,
        "code": code[:1000],
        "error": error,
        "metrics": metrics,
        "iteration": ctx.iteration,
    })
    state.total_rejected += 1
    state.stagnation_counter += 1
    logger.info(
        "acceptance.rejected",
        child_id=child_id,
        child_score=child_score,
        parent_score=parent_score,
        error=error,
    )
