"""GEPAState — Pydantic model for gepa_state.json."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GEPAState(BaseModel):
    iteration: int = 0
    stagnation_counter: int = 0
    best_score: float = 0.0
    best_id: str | None = None
    merge_attempts: int = 0
    merge_due: bool = False
    use_merge: bool = True
    eval_count: int = 0
    budget_limit: int = 50
    population_size: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    last_action: str = "mutate"


def load_state(ctx: Any) -> GEPAState:
    data = ctx.read_json("gepa_state.json")
    if data:
        return GEPAState(**data)
    return GEPAState(budget_limit=ctx.budget_limit)


def save_state(ctx: Any, state: GEPAState) -> None:
    ctx.write_json("gepa_state.json", state.model_dump())


def init_state(ctx: Any) -> GEPAState:
    state = GEPAState(budget_limit=ctx.budget_limit)
    save_state(ctx, state)
    return state
