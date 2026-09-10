"""Seed the run's mutable state from the task's initial code.

The entry nodes of a mode: ``task_input`` writes the problem, ``seed_run`` gives
the search a starting point. Seeding here rather than inside the first iteration
means every node's declared ``reads`` exists before the node runs, so the graph's
data dependencies are satisfiable on the first pass and not only after a loop.

Filenames are passed on the command line, so the writer and the graph's
``writes`` declaration cannot drift apart.

Usage: ``python -m srf.ops.common.seed population.json best_solution.py``
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_STATE: dict[str, Any] = {}
"""Payload for a ``*_state.json`` file: every op reads it with defaults applied."""


def _work_dir() -> Path:
    return Path(os.environ.get("SRF_WORK_DIR", ".")).resolve()


def _initial_code(work_dir: Path) -> str:
    """The task's starting program, from ``task.yaml`` or its own ``initial.py``."""
    task_file = work_dir / "task.yaml"
    if task_file.exists():
        from srf.tasks.registry import _parse_yaml

        parsed = _parse_yaml(task_file.read_text()) or {}
        code = parsed.get("initial_code")
        if code:
            return str(code)

    initial_file = work_dir / "initial.py"
    if initial_file.exists():
        return initial_file.read_text()
    return ""


def _seed_id(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()[:12]


def _payload(filename: str, code: str, seed_id: str) -> Any:
    """The initial payload for one seeded file."""
    if filename == "population.json":
        return {
            seed_id: {
                "id": seed_id,
                "code": code,
                "score": 0.0,
                "metrics": {},
                "generation": 0,
                "parent_id": None,
            }
        }
    if filename == "genealogy.json":
        return {"nodes": {seed_id: {"generation": 0}}, "edges": []}
    if filename.endswith("_history.json"):
        return []
    if filename.endswith("_populations.json"):
        return {"island_0": {}}
    if filename == "best_solution.py":
        return code
    if filename == "tree_state.json":
        return {
            "nodes": {
                seed_id: {
                    "id": seed_id,
                    "code": code,
                    "score": 0.0,
                    "is_buggy": False,
                    "debug_depth": 0,
                    "parent_id": None,
                    "children_ids": [],
                    "terminal_output": "",
                    "metrics": {},
                    "action": "draft",
                }
            },
            "best_id": seed_id,
            "best_score": 0.0,
        }
    return DEFAULT_STATE


def seed(work_dir: Path, filenames: list[str]) -> list[str]:
    """Write the initial payload for each name that does not already exist."""
    work_dir.mkdir(parents=True, exist_ok=True)
    code = _initial_code(work_dir)
    seed_id = _seed_id(code)
    written: list[str] = []
    for filename in filenames:
        path = work_dir / filename
        if path.exists():
            continue
        payload = _payload(filename, code, seed_id)
        if filename.endswith(".py"):
            path.write_text(str(payload))
        else:
            path.write_text(json.dumps(payload, indent=2))
        written.append(filename)
    return written


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: seed the named files, then report what was written."""
    names = list(sys.argv[1:] if argv is None else argv)
    if not names:
        print("Usage: python -m srf.ops.common.seed <file> [<file> ...]", file=sys.stderr)
        return 1
    written = seed(_work_dir(), names)
    print(json.dumps({"seeded": written}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
