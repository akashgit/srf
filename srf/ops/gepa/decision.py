"""Merge/mutate decision gate — should_merge.

Used as a GateNode evaluator: ``python -m srf.ops.gepa.decision should_merge``.
Prints the gate's forward outcome, ``mutate`` or ``merge``. Both are alternative
branches of the same iteration rather than a rewind, so neither is named
``reloop``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


def should_merge_callable(ctx: Any) -> None:
    """Write decision to policy_decisions trace."""
    from srf.ops.common.tracing import log_policy_decision
    from srf.ops.gepa.state import load_state

    state = load_state(ctx)
    population = ctx.read_json("population.json") or {}
    merge_threshold = int(ctx.knobs.get("merge_stagnation_threshold", 15))

    decision, reason = _decide(state, population, merge_threshold)
    log_policy_decision(ctx, decision, reason, {
        "stagnation": state.stagnation_counter,
        "threshold": merge_threshold,
        "population_size": len(population),
        "merge_attempts": state.merge_attempts,
        "use_merge": state.use_merge,
    })


def _decide(state: Any, population: dict, merge_threshold: int) -> tuple[str, str]:
    """Core decision logic.

    Returns ``mutate`` or ``merge`` based on:
    - use_merge AND (merge_due OR stagnation >= threshold)
    - AND attempts < max AND pop >= 2
    """
    if not state.use_merge:
        return "mutate", "merge disabled"

    stagnation_triggered = state.stagnation_counter >= merge_threshold
    merge_due = state.merge_due

    if not (merge_due or stagnation_triggered):
        return "mutate", "no stagnation, mutate"

    max_merge_attempts = 5
    if state.merge_attempts >= max_merge_attempts:
        return "mutate", f"merge attempts exhausted ({state.merge_attempts})"

    if len(population) < 2:
        return "mutate", "population too small for merge"

    return "merge", f"merge triggered (stagnation={state.stagnation_counter})"


def should_merge() -> None:
    """GateNode evaluator — prints ``mutate`` or ``merge``."""
    work_dir = Path(os.environ.get("SRF_WORK_DIR", "."))
    state_path = work_dir / "gepa_state.json"
    pop_path = work_dir / "population.json"

    if not state_path.exists():
        print("mutate")
        return

    state_data = json.loads(state_path.read_text())
    population = json.loads(pop_path.read_text()) if pop_path.exists() else {}

    merge_threshold = 15
    knobs_path = work_dir / "knobs.json"
    if knobs_path.exists():
        knobs = json.loads(knobs_path.read_text())
        merge_threshold = int(knobs.get("merge_stagnation_threshold", 15))

    class _State:
        def __init__(self, d):
            self.use_merge = d.get("use_merge", True)
            self.merge_due = d.get("merge_due", False)
            self.stagnation_counter = d.get("stagnation_counter", 0)
            self.merge_attempts = d.get("merge_attempts", 0)

    decision, reason = _decide(_State(state_data), population, merge_threshold)
    print(decision)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "should_merge":
        should_merge()
    else:
        print("Usage: python -m srf.ops.gepa.decision should_merge", file=sys.stderr)
        sys.exit(1)
