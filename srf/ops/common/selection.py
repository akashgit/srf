"""Parent selection strategies for archive-based modes."""

from __future__ import annotations

import math
import random
from typing import Any


def select_best(programs: list[dict[str, Any]]) -> dict[str, Any]:
    return max(programs, key=lambda p: p.get("score", 0.0))


def select_pareto(programs: list[dict[str, Any]]) -> dict[str, Any]:
    front = []
    for p in programs:
        score = p.get("score", 0.0)
        length = len(p.get("code", ""))
        dominated = any(
            o.get("score", 0.0) >= score and len(o.get("code", "")) <= length
            and (o.get("score", 0.0) > score or len(o.get("code", "")) < length)
            for o in programs
        )
        if not dominated:
            front.append(p)
    return random.choice(front) if front else programs[0]


def select_epsilon_greedy(programs: list[dict[str, Any]], epsilon: float = 0.1) -> dict[str, Any]:
    if random.random() < epsilon:
        return random.choice(programs)
    return select_best(programs)


def select_power_law(programs: list[dict[str, Any]], alpha: float = 2.0) -> dict[str, Any]:
    sorted_progs = sorted(programs, key=lambda p: p.get("score", 0.0), reverse=True)
    weights = [1.0 / ((i + 1) ** alpha) for i in range(len(sorted_progs))]
    total = sum(weights)
    weights = [w / total for w in weights]
    return random.choices(sorted_progs, weights=weights, k=1)[0]


def select_ucb(programs: list[dict[str, Any]], visit_counts: dict[str, int] | None = None,
               total_visits: int = 1, c: float = 1.414) -> dict[str, Any]:
    if visit_counts is None:
        return select_best(programs)
    best_ucb = -float("inf")
    best_prog = programs[0]
    for p in programs:
        pid = p.get("id", "")
        visits = visit_counts.get(pid, 0)
        score = p.get("score", 0.0)
        if visits == 0:
            return p
        ucb = score + c * math.sqrt(math.log(total_visits) / visits)
        if ucb > best_ucb:
            best_ucb = ucb
            best_prog = p
    return best_prog


def select_uniform(programs: list[dict[str, Any]]) -> dict[str, Any]:
    return random.choice(programs)


STRATEGIES = {
    "best": select_best,
    "pareto": select_pareto,
    "epsilon_greedy": select_epsilon_greedy,
    "power_law": select_power_law,
    "ucb": select_ucb,
    "uniform": select_uniform,
}


def select_parent(programs: list[dict[str, Any]], strategy: str = "best", **kwargs: Any) -> dict[str, Any]:
    if not programs:
        raise ValueError("Cannot select from empty population")
    func = STRATEGIES.get(strategy, select_best)
    if strategy in ("ucb",):
        return func(programs, **kwargs)
    return func(programs)
