"""Run one graph node's deterministic op as a subprocess.

The DSH workflow spine runs a node whose graph declares a ``command``. For SRF's
op nodes that command is ``python -m srf.ops.run <module>:<function>``. This
adapter rebuilds the context object the ops expect — the work directory, the
task, the resolved knobs, and the node's declared reads/writes — from the
environment the runtime sets, then calls the op.

Environment contract (set by the runtime, i.e. the spine's ``commandEnv`` plus
the node declaration it passes under ``DSH_WORKFLOW_NODE``):

``SRF_WORK_DIR``       the run's work directory (default ``.``)
``DSH_WORKFLOW_NODE``  JSON: ``{ id, type, command, reads, writes }``
``SRF_TASK``           task name to load from the registry (optional)
``SRF_KNOBS``          JSON object of resolved knob values (optional)
``SRF_BUDGET``         eval budget (default 50)
``SRF_RUN_ID``         run identifier (default ``run``)
``SRF_ITERATION``      loop iteration (default 0)
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


class RunContext:
    """The duck-typed context SRF's deterministic ops receive.

    This is the subprocess-shaped successor of the deleted in-process context:
    same attribute and method surface, but sourced from the environment rather
    than an executor.
    """

    def __init__(
        self,
        work_dir: Path,
        task: dict[str, Any],
        knobs: dict[str, Any],
        budget_limit: int,
        node_reads: set[str],
        node_writes: set[str],
        run_id: str,
        iteration: int,
    ) -> None:
        self.work_dir = work_dir
        self.task = task
        self.knobs = knobs
        self.budget_limit = budget_limit
        self._current_node_reads = node_reads
        self._current_node_writes = node_writes
        self.run_id = run_id
        self.iteration = iteration

    def read_json(self, filename: str) -> Any:
        path = self.work_dir / filename
        return json.loads(path.read_text()) if path.exists() else None

    def write_json(self, filename: str, data: Any) -> None:
        (self.work_dir / filename).write_text(json.dumps(data, indent=2, default=str))

    def read_text(self, filename: str) -> str:
        path = self.work_dir / filename
        return path.read_text() if path.exists() else ""

    def write_text(self, filename: str, content: str) -> None:
        (self.work_dir / filename).write_text(content)


def _load_task(work_dir: Path, task_name: str) -> dict[str, Any]:
    """The task config, from the registry when named, else from ``task.yaml``.

    The registry's entry carries ``_dir``, which the sandbox uses to find the
    task's own ``eval.py``/``initial.py``.
    """
    if task_name:
        from srf.tasks.registry import TaskRegistry

        raw = TaskRegistry().get_raw(task_name)
        if raw:
            return raw
    task_file = work_dir / "task.yaml"
    if task_file.exists():
        from srf.tasks.registry import _parse_yaml

        parsed = _parse_yaml(task_file.read_text()) or {}
        if parsed:
            return parsed
    return {}


def _node_files(manifest: dict[str, Any]) -> tuple[set[str], set[str]]:
    """The node's declared reads/writes, from the spine's node declaration."""
    return set(manifest.get("reads", [])), set(manifest.get("writes", []))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args or ":" not in args[0]:
        print("Usage: python -m srf.ops.run <module>:<function>", file=sys.stderr)
        return 2
    module_path, _, function = args[0].partition(":")

    # Ops log via structlog; keep that off stdout, which the runtime treats as a
    # data channel (and, for gates, as the verdict protocol).
    from srf.logging.config import configure_logging

    configure_logging()

    work_dir = Path(os.environ.get("SRF_WORK_DIR", ".")).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = json.loads(os.environ.get("DSH_WORKFLOW_NODE", "{}"))
    reads, writes = _node_files(manifest)
    knobs: dict[str, Any] = json.loads(os.environ.get("SRF_KNOBS", "{}") or "{}")
    budget = int(os.environ.get("SRF_BUDGET", "50"))
    run_id = os.environ.get("SRF_RUN_ID", "run")
    iteration = int(os.environ.get("SRF_ITERATION", "0"))
    task = _load_task(work_dir, os.environ.get("SRF_TASK", ""))

    ctx = RunContext(
        work_dir=work_dir,
        task=task,
        knobs=knobs,
        budget_limit=budget,
        node_reads=reads,
        node_writes=writes,
        run_id=run_id,
        iteration=iteration,
    )

    module = importlib.import_module(module_path)
    function_obj = getattr(module, function, None)
    if function_obj is None:
        print(f"{module_path} has no function {function}", file=sys.stderr)
        return 3

    function_obj(ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
