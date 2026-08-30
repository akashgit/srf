"""Lab Director — multi-mode orchestration agent."""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

from srf._factory_shim import ExecutionContext, MockLLMClient, WorkflowExecutor
from srf.lab.protocol import LabDirectorProtocol, ModeResult
from srf.registry import get_mode_registry, get_task_registry

logger = structlog.get_logger()


class LabDirector(LabDirectorProtocol):
    def __init__(self, llm_client: Any = None):
        self._mode_registry = get_mode_registry()
        self._task_registry = get_task_registry()
        self._llm_client = llm_client or MockLLMClient()

    def select_mode(self, task: dict[str, Any]) -> str:
        modes = self._mode_registry.list_modes()
        return modes[0] if modes else "gepa"

    def run_mode(self, mode: str, task: dict[str, Any], budget: int) -> ModeResult:
        workflow = self._mode_registry.get(mode)
        if workflow is None:
            return ModeResult(score=0.0, best_code="", trace_path=Path("."), cost=0.0)

        run_id = uuid.uuid4().hex[:12]
        work_dir = Path(tempfile.mkdtemp(prefix=f"srf_lab_{mode}_"))

        knobs = {k.name: k.default for k in workflow.knobs}
        ctx = ExecutionContext(
            work_dir=work_dir, knobs=knobs, task=task,
            budget_limit=budget, llm_client=self._llm_client, run_id=run_id,
        )

        _copy_task_files(task, work_dir)

        from srf.ops.common.budget import init_budget
        from srf.ops.common.tracing import init_trace_dir
        init_trace_dir(work_dir)
        init_budget(ctx)
        _init_mode_state(mode, ctx)

        try:
            executor = WorkflowExecutor(ctx)
            executor.execute(workflow.root)
        except Exception as e:
            logger.error("lab.mode_error", mode=mode, error=str(e))
            return ModeResult(score=0.0, best_code="", trace_path=work_dir, cost=0.0)

        best_code = ctx.read_text("best_solution.py")
        best_score = _get_best_score(ctx, mode)

        return ModeResult(
            score=best_score, best_code=best_code,
            trace_path=work_dir, cost=0.0, knob_values_used=knobs,
        )

    def compare_results(self, results: list[ModeResult]) -> ModeResult:
        if not results:
            return ModeResult(score=0.0, best_code="", trace_path=Path("."), cost=0.0)
        return max(results, key=lambda r: r.score)

    def run_lab(self, task_name: str, modes: list[str], budget: int) -> dict[str, Any]:
        """Run multiple modes on a task and compare results."""
        task = self._task_registry.get(task_name)
        if task is None:
            return {"error": f"Unknown task: {task_name}"}

        per_mode_budget = budget // len(modes) if modes else budget
        results: dict[str, ModeResult] = {}

        for mode in modes:
            logger.info("lab.running_mode", mode=mode, budget=per_mode_budget)
            try:
                result = self.run_mode(mode, task, per_mode_budget)
                results[mode] = result
            except Exception as e:
                logger.error("lab.mode_failed", mode=mode, error=str(e))
                results[mode] = ModeResult(score=0.0, best_code="", trace_path=Path("."), cost=0.0)

        all_results = list(results.values())
        winner = self.compare_results(all_results)

        report = {
            "task": task_name,
            "modes": {},
            "winner": None,
            "winner_score": winner.score,
        }
        for mode, result in results.items():
            report["modes"][mode] = {
                "score": result.score,
                "trace_path": str(result.trace_path),
            }
            if result.score == winner.score:
                report["winner"] = mode

        return report


def _copy_task_files(task: dict[str, Any], work_dir: Path) -> None:
    task_dir = task.get("_dir")
    if not task_dir:
        return
    for fname in ["eval.py", "initial.py"]:
        src = Path(task_dir) / fname
        if src.exists():
            shutil.copy2(src, work_dir / fname)


def _init_mode_state(mode: str, ctx: ExecutionContext) -> None:
    if mode == "gepa":
        from srf.ops.gepa.population import init_population
        from srf.ops.gepa.state import init_state
        init_state(ctx)
        init_population(ctx)
    else:
        initial_code = ctx.task.get("initial_code", "")
        ctx.write_text("best_solution.py", initial_code)


def _get_best_score(ctx: ExecutionContext, mode: str) -> float:
    for state_file in [f"{mode}_state.json", "gepa_state.json", "aide_state.json",
                       "scs_state.json", "openevolve_state.json", "shinka_state.json",
                       "adaevolve_state.json", "evox_state.json", "karpathy_state.json",
                       "autoresearch_state.json", "autoscientists_state.json"]:
        state = ctx.read_json(state_file)
        if state and "best_score" in state:
            return state["best_score"]
    return 0.0
