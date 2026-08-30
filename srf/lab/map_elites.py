"""MAP-Elites outer loop for OptKnob evolution.

Multi-Emitter MAP-Elites over the joint space of mode selection + knob values.
3D feature grid: harness type × search strategy × eval budget.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class MAPElitesCell:
    mode: str
    knob_values: dict[str, Any]
    score: float
    features: tuple[int, ...]


@dataclass
class MAPElitesGrid:
    dims: tuple[int, ...] = (3, 4, 3)
    cells: dict[tuple[int, ...], MAPElitesCell] = field(default_factory=dict)

    def update(self, cell: MAPElitesCell) -> bool:
        key = cell.features
        if key not in self.cells or cell.score > self.cells[key].score:
            self.cells[key] = cell
            return True
        return False

    def get_occupied_cells(self) -> list[MAPElitesCell]:
        return list(self.cells.values())

    def coverage(self) -> float:
        total = 1
        for d in self.dims:
            total *= d
        return len(self.cells) / total

    def best_cell(self) -> MAPElitesCell | None:
        if not self.cells:
            return None
        return max(self.cells.values(), key=lambda c: c.score)


HARNESS_TYPES = {
    "gepa": 0, "scs": 0, "openevolve": 0, "shinka": 0, "adaevolve": 0, "evox": 0,
    "aide": 1, "ai_sci_v2": 1,
    "best_of_n": 2, "autoresearch": 2, "karpathy": 2, "autoscientists": 2, "ai_sci_v1": 2,
}

STRATEGY_MAP = {
    "best": 0, "epsilon_greedy": 1, "power_law": 2, "uniform": 3,
}


def compute_features(mode: str, knob_values: dict[str, Any], budget: int) -> tuple[int, ...]:
    harness_type = HARNESS_TYPES.get(mode, 0)
    strategy = str(knob_values.get("parent_selection", "best"))
    strategy_idx = STRATEGY_MAP.get(strategy, 0)
    budget_bin = 0 if budget <= 20 else (1 if budget <= 50 else 2)
    return (harness_type, strategy_idx, budget_bin)


class RandomEmitter:
    def __init__(self, modes: list[str], knob_specs: dict[str, list[Any]]):
        self.modes = modes
        self.knob_specs = knob_specs

    def emit(self) -> tuple[str, dict[str, Any]]:
        mode = random.choice(self.modes)
        knobs = {k: random.choice(v) for k, v in self.knob_specs.items()}
        return mode, knobs


class ImprovementEmitter:
    def __init__(self, grid: MAPElitesGrid, knob_specs: dict[str, list[Any]]):
        self.grid = grid
        self.knob_specs = knob_specs

    def emit(self) -> tuple[str, dict[str, Any]] | None:
        occupied = self.grid.get_occupied_cells()
        if not occupied:
            return None
        parent = random.choice(occupied)
        knobs = copy.deepcopy(parent.knob_values)
        if self.knob_specs:
            key = random.choice(list(self.knob_specs.keys()))
            knobs[key] = random.choice(self.knob_specs[key])
        return parent.mode, knobs


class MAPElitesLoop:
    def __init__(self, modes: list[str], knob_specs: dict[str, list[Any]]):
        self.grid = MAPElitesGrid()
        self.modes = modes
        self.knob_specs = knob_specs
        self.random_emitter = RandomEmitter(modes, knob_specs)
        self.improvement_emitter = ImprovementEmitter(self.grid, knob_specs)

    def suggest(self) -> tuple[str, dict[str, Any]]:
        """Suggest a mode + knob configuration to evaluate."""
        if random.random() < 0.3 or not self.grid.cells:
            return self.random_emitter.emit()
        result = self.improvement_emitter.emit()
        return result if result else self.random_emitter.emit()

    def report(self, mode: str, knob_values: dict[str, Any], score: float, budget: int) -> bool:
        """Report evaluation result back to the grid."""
        features = compute_features(mode, knob_values, budget)
        cell = MAPElitesCell(mode=mode, knob_values=knob_values, score=score, features=features)
        return self.grid.update(cell)

    def get_results(self) -> dict[str, Any]:
        return {
            "coverage": self.grid.coverage(),
            "n_cells": len(self.grid.cells),
            "best": self.grid.best_cell().__dict__ if self.grid.best_cell() else None,
            "cells": [
                {"features": list(c.features), "mode": c.mode, "score": c.score}
                for c in self.grid.get_occupied_cells()
            ],
        }
