"""Population management — select_parent with configurable strategies."""

from __future__ import annotations

import hashlib
import random
from typing import Any

import structlog

from srf.ops.gepa.state import load_state, save_state

logger = structlog.get_logger()


def select_parent(ctx: Any) -> None:
    """Read population.json, select parent by strategy, write selected_parent.json.

    Strategies (controlled by parent_selection OptKnob):
      - best: always pick the highest-scoring individual
      - pareto: pick from the Pareto front (score vs code length)
      - epsilon_greedy: pick best with probability 1-epsilon, else random
    """
    population = ctx.read_json("population.json") or {}
    state = load_state(ctx)
    strategy = ctx.knobs.get("parent_selection", "best")

    state = load_state(ctx)
    state.last_action = "mutate"
    save_state(ctx, state)

    if not population:
        logger.warning("population.empty")
        ctx.write_json("selected_parent.json", {
            "id": "seed",
            "code": ctx.task.get("initial_code", ""),
            "score": 0.0,
            "metrics": {},
        })
        return

    individuals = list(population.values())
    selected = _select_by_strategy(individuals, strategy)

    ctx.write_json("selected_parent.json", {
        "id": selected["id"],
        "code": selected["code"],
        "score": selected.get("score", 0.0),
        "metrics": selected.get("metrics", {}),
    })
    logger.info(
        "population.selected_parent",
        strategy=strategy,
        parent_id=selected["id"],
        parent_score=selected.get("score", 0.0),
    )


def _select_by_strategy(individuals: list[dict], strategy: str) -> dict:
    if strategy == "best":
        return max(individuals, key=lambda x: x.get("score", 0.0))
    elif strategy == "pareto":
        return _pareto_select(individuals)
    elif strategy == "epsilon_greedy":
        if random.random() < 0.1:
            return random.choice(individuals)
        return max(individuals, key=lambda x: x.get("score", 0.0))
    return max(individuals, key=lambda x: x.get("score", 0.0))


def _pareto_select(individuals: list[dict]) -> dict:
    """Select from Pareto front of score vs code length (shorter is better)."""
    front = []
    for ind in individuals:
        score = ind.get("score", 0.0)
        length = len(ind.get("code", ""))
        dominated = False
        for other in individuals:
            o_score = other.get("score", 0.0)
            o_length = len(other.get("code", ""))
            if o_score >= score and o_length <= length and (o_score > score or o_length < length):
                dominated = True
                break
        if not dominated:
            front.append(ind)
    return random.choice(front) if front else individuals[0]


def init_population(ctx: Any) -> None:
    """Initialize population with the seed solution from initial.py."""
    initial_code = ctx.task.get("initial_code", "")
    ind_id = hashlib.sha256(initial_code.encode()).hexdigest()[:12]
    population = {
        ind_id: {
            "id": ind_id,
            "code": initial_code,
            "score": 0.0,
            "metrics": {},
            "generation": 0,
            "parent_id": None,
        }
    }
    ctx.write_json("population.json", population)
    ctx.write_json("genealogy.json", {"nodes": {ind_id: {"generation": 0}}, "edges": []})
    ctx.write_json("rejection_history.json", [])
    ctx.write_json("accepted_history.json", [])
    ctx.write_text("best_solution.py", initial_code)
    logger.info("population.initialized", seed_id=ind_id)
