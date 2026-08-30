"""Shared population management — PopulationState and Program dataclasses."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Program:
    id: str
    code: str
    score: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    generation: int = 0
    parent_id: str | None = None
    features: dict[str, float] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "score": self.score,
            "metrics": self.metrics,
            "generation": self.generation,
            "parent_id": self.parent_id,
            "features": self.features,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Program":
        return cls(
            id=d["id"], code=d["code"], score=d.get("score", 0.0),
            metrics=d.get("metrics", {}), generation=d.get("generation", 0),
            parent_id=d.get("parent_id"), features=d.get("features", {}),
            error=d.get("error"),
        )


@dataclass
class PopulationState:
    programs: dict[str, Program] = field(default_factory=dict)
    best_id: str | None = None
    best_score: float = 0.0
    generation: int = 0

    def add(self, program: Program) -> bool:
        self.programs[program.id] = program
        if program.score > self.best_score:
            self.best_score = program.score
            self.best_id = program.id
            return True
        return False

    def get_best(self) -> Program | None:
        if self.best_id and self.best_id in self.programs:
            return self.programs[self.best_id]
        if self.programs:
            best = max(self.programs.values(), key=lambda p: p.score)
            self.best_id = best.id
            self.best_score = best.score
            return best
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            pid: p.to_dict() for pid, p in self.programs.items()
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PopulationState":
        state = cls()
        for pid, pdata in d.items():
            prog = Program.from_dict(pdata)
            state.add(prog)
        return state

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str))

    @classmethod
    def load(cls, path: Path) -> "PopulationState":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls.from_dict(data)


def make_program_id(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()[:12]


def quality_diversity_accept(candidate: Program, population: PopulationState,
                             diversity_threshold: float = 0.1) -> bool:
    if candidate.error:
        return False
    if not population.programs:
        return True
    if candidate.score > population.best_score:
        return True
    best = population.get_best()
    if best and candidate.score >= best.score * (1.0 - diversity_threshold):
        return True
    return False
