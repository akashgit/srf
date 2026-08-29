"""Tests for benchmark tasks — task.yaml validation, eval.py on initial.py."""

import json
import subprocess
import sys
from pathlib import Path

from srf.tasks.registry import TaskRegistry


def test_all_task_yamls_load():
    registry = TaskRegistry()
    for name in registry.names():
        task = registry.get(name)
        assert task is not None
        assert task["name"] == name
        assert "description" in task
        assert "eval_command" in task


def test_circle_packing_eval_on_initial():
    task_dir = Path(__file__).parent.parent / "srf" / "tasks" / "math" / "circle_packing"
    result = subprocess.run(
        [sys.executable, str(task_dir / "eval.py")],
        capture_output=True,
        text=True,
        cwd=str(task_dir),
        timeout=30,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout.strip())
    assert "score" in output
    assert output["score"] > 0


def test_autocorrelation_eval_on_initial():
    task_dir = Path(__file__).parent.parent / "srf" / "tasks" / "math" / "autocorrelation_inequality"
    result = subprocess.run(
        [sys.executable, str(task_dir / "eval.py")],
        capture_output=True,
        text=True,
        cwd=str(task_dir),
        timeout=30,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout.strip())
    assert "score" in output
    assert output["score"] > 0


def test_trimul_eval_on_initial():
    task_dir = Path(__file__).parent.parent / "srf" / "tasks" / "gpu" / "trimul"
    result = subprocess.run(
        [sys.executable, str(task_dir / "eval.py")],
        capture_output=True,
        text=True,
        cwd=str(task_dir),
        timeout=60,
    )
    assert result.returncode == 0
    output = json.loads(result.stdout.strip())
    assert "score" in output
    assert output["score"] > 0


def test_wrong_solution_scores_zero():
    """A completely wrong candidate should score 0."""
    task_dir = Path(__file__).parent.parent / "srf" / "tasks" / "math" / "circle_packing"
    import tempfile
    import shutil

    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.copy2(task_dir / "eval.py", Path(tmpdir) / "eval.py")
        (Path(tmpdir) / "candidate.py").write_text("def solve(n, radii): return None\n")
        result = subprocess.run(
            [sys.executable, "eval.py"],
            capture_output=True,
            text=True,
            cwd=tmpdir,
            timeout=30,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout.strip())
        assert output["score"] == 0.0
