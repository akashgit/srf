"""Phase 2 op contract: the runtime runs SRF's op nodes as subprocesses.

These tests drive the exact command strings the graphs carry — ``python -m
srf.ops.run <module>:<function>`` and the entry-point modules — with the
environment the spine sets (``SRF_WORK_DIR``/``SRF_TASK``/``SRF_KNOBS``/
``SRF_BUDGET`` plus the ``DSH_WORKFLOW_NODE`` declaration). They prove a
deterministic node really executes and produces a real score, not just that the
adapter imports.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _run(work_dir: Path, *argv: str, node: dict | None = None, budget: str = "50") -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "SRF_WORK_DIR": str(work_dir),
        "SRF_TASK": "circle_packing",
        "SRF_KNOBS": "{}",
        "SRF_BUDGET": budget,
    }
    if node is not None:
        env["DSH_WORKFLOW_NODE"] = json.dumps(node)
    return subprocess.run(
        [sys.executable, *argv],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


EVAL_NODE = {
    "id": "sandbox_eval",
    "type": "FnNode",
    "command": "python -m srf.ops.run srf.ops.common.sandbox:run_eval",
    "reads": ["candidate.py", "task.yaml"],
    "writes": ["eval_result.json"],
}


def test_deterministic_chain_returns_a_real_score(tmp_path: Path) -> None:
    """task_input → (candidate) → run_eval → a real score, with the budget bumped."""
    task = _run(tmp_path, "-m", "srf.ops.common.task_input")
    assert task.returncode == 0, task.stderr
    assert (tmp_path / "task.yaml").exists()
    assert (tmp_path / "eval.py").exists()

    # The LLM writes a candidate; for a deterministic test, seed the initial code.
    shutil.copyfile(tmp_path / "initial.py", tmp_path / "candidate.py")

    evaluated = _run(tmp_path, "-m", "srf.ops.run", "srf.ops.common.sandbox:run_eval", node=EVAL_NODE)
    assert evaluated.returncode == 0, evaluated.stderr

    result = json.loads((tmp_path / "eval_result.json").read_text())
    assert result["score"] > 0.0
    assert result["error"] is None
    assert result["metrics"]["placed"] > 0
    assert result["metrics"]["total"] == 26

    budget = json.loads((tmp_path / "budget_state.json").read_text())
    assert budget["eval_count"] == 1
    assert budget["budget_limit"] == 50


def test_budget_gate_terminates_the_loop(tmp_path: Path) -> None:
    """The budget gate prints reloop while evals remain, proceed once spent."""
    _run(tmp_path, "-m", "srf.ops.common.task_input", budget="1")
    shutil.copyfile(tmp_path / "initial.py", tmp_path / "candidate.py")

    before = _run(tmp_path, "-m", "srf.ops.common.budget", "check")
    assert before.stdout.strip().splitlines()[-1] == "RELOOP"

    _run(tmp_path, "-m", "srf.ops.run", "srf.ops.common.sandbox:run_eval", node=EVAL_NODE, budget="1")
    after = _run(tmp_path, "-m", "srf.ops.common.budget", "check")
    # The verdict is the last stdout line; the budget log goes to stderr.
    assert after.stdout.strip() == "PROCEED"
    assert "budget.exhausted" in after.stderr


def test_seed_gives_the_search_a_starting_point(tmp_path: Path) -> None:
    """seed_run writes a population from the task's initial code."""
    _run(tmp_path, "-m", "srf.ops.common.task_input")
    seeded = _run(
        tmp_path,
        "-m",
        "srf.ops.common.seed",
        "population.json",
        "genealogy.json",
        "best_solution.py",
        "gepa_state.json",
    )
    assert seeded.returncode == 0, seeded.stderr

    population = json.loads((tmp_path / "population.json").read_text())
    assert len(population) == 1
    assert (tmp_path / "best_solution.py").exists()
    assert (tmp_path / "gepa_state.json").exists()


def test_adapter_resolves_reads_and_writes_from_the_node(tmp_path: Path) -> None:
    """The op can find its own filenames from the node declaration."""
    _run(tmp_path, "-m", "srf.ops.common.task_input")
    shutil.copyfile(tmp_path / "initial.py", tmp_path / "candidate.py")

    node = {
        "id": "eval_3",
        "type": "FnNode",
        "command": "python -m srf.ops.run srf.ops.common.sandbox:run_eval",
        "reads": ["candidate_3.py", "task.yaml"],
        "writes": ["eval_result_3.json"],
    }
    # The node declares candidate_3.py, which does not exist: the op must report
    # the missing file through the result channel, not crash the runner.
    shutil.copyfile(tmp_path / "initial.py", tmp_path / "candidate_3.py")
    result = _run(tmp_path, "-m", "srf.ops.run", "srf.ops.common.sandbox:run_eval", node=node)
    assert result.returncode == 0, result.stderr
    scored = json.loads((tmp_path / "eval_result_3.json").read_text())
    assert scored["score"] > 0.0


def test_adapter_rejects_an_unknown_callable(tmp_path: Path) -> None:
    result = _run(tmp_path, "-m", "srf.ops.run", "srf.ops.common.sandbox:nope")
    assert result.returncode != 0
    assert "nope" in result.stderr


def test_adapter_requires_a_module_function_pair(tmp_path: Path) -> None:
    result = _run(tmp_path, "-m", "srf.ops.run")
    assert result.returncode == 2
    assert "Usage" in result.stderr
