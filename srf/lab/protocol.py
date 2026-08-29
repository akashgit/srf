"""Lab Director protocol — seams for Phase 2 multi-mode orchestration."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ModeResult:
    score: float
    best_code: str
    trace_path: Path
    cost: float
    knob_values_used: dict[str, Any] = field(default_factory=dict)


class LabDirectorProtocol(ABC):
    @abstractmethod
    def select_mode(self, task: dict[str, Any]) -> str: ...

    @abstractmethod
    def run_mode(self, mode: str, task: dict[str, Any], budget: int) -> ModeResult: ...

    @abstractmethod
    def compare_results(self, results: list[ModeResult]) -> ModeResult: ...
