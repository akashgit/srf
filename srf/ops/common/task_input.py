"""Materialize the selected task into the run's work directory.

The graph's entry node. A run happens in a work directory that holds exactly the
artifacts the graph declares, so the problem itself is written by a node rather
than injected from outside the graph.

Environment:
  ``SRF_WORK_DIR`` — the run's work directory (default ``.``).
  ``SRF_TASK`` — the task name to materialize (a ``task.yaml`` directory name).
  ``SRF_TASK_DIR`` — an explicit task directory, overriding ``SRF_TASK``.

Prints ``PROCEED`` so it can also serve as an ``fn`` gate evaluator.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

TASK_FILES = ("task.yaml", "eval.py", "initial.py")

RUN_FILES = ("knobs.json", "budget_state.json")
"""Run settings the entry node also writes: knob values and the eval budget."""


def _work_dir() -> Path:
    return Path(os.environ.get("SRF_WORK_DIR", ".")).resolve()


def _resolve_task_dir() -> Path | None:
    explicit = os.environ.get("SRF_TASK_DIR")
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        return candidate if candidate.is_dir() else None

    name = os.environ.get("SRF_TASK")
    if not name:
        return None
    from srf.tasks.registry import TaskRegistry

    task = TaskRegistry().get_raw(name)
    if task is None:
        return None
    directory = task.get("_dir")
    return Path(directory).resolve() if directory else None


def _run_settings() -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolved knob values and the initial budget state for this run."""
    raw = os.environ.get("SRF_KNOBS", "")
    knobs: dict[str, Any] = json.loads(raw) if raw else {}
    limit = int(os.environ.get("SRF_BUDGET", "50"))
    budget = {
        "eval_count": 0,
        "llm_input_tokens": 0,
        "llm_output_tokens": 0,
        "llm_calls": 0,
        "budget_limit": limit,
    }
    return knobs, budget


def materialize(work_dir: Path, task_dir: Path | None) -> list[str]:
    """Write the task's files and the run settings into ``work_dir``.

    Returns the names written. ``knobs.json`` is written even when it already
    exists, because the resolved values for this run are authoritative.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    if task_dir is None:
        raise FileNotFoundError(
            "no task to materialize: set SRF_TASK or SRF_TASK_DIR"
        )

    written: list[str] = []
    for filename in TASK_FILES:
        source = task_dir / filename
        if source.exists():
            shutil.copy2(source, work_dir / filename)
            written.append(filename)
    if "task.yaml" not in written:
        raise FileNotFoundError(f"{task_dir} has no task.yaml")

    knobs, budget = _run_settings()
    for filename, payload in (("knobs.json", knobs), ("budget_state.json", budget)):
        (work_dir / filename).write_text(json.dumps(payload, indent=2))
        written.append(filename)
    return written


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: write the task files, then report what was written."""
    argv = sys.argv[1:] if argv is None else argv
    work_dir = _work_dir()
    task_dir = _resolve_task_dir()
    written = materialize(work_dir, task_dir)
    print(json.dumps({"work_dir": str(work_dir), "task_dir": str(task_dir), "written": written}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
