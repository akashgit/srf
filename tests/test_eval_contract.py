"""Tests for eval contract validation (Issue #1)."""

import tempfile
from pathlib import Path

from srf.tasks.schema import validate_eval_contract


def test_valid_evaluate_function():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def evaluate(solution_path):\n    return {'score': 1.0}\n")
        f.flush()
        errors = validate_eval_contract(Path(f.name))
    assert errors == []


def test_valid_score_function():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def score(code):\n    return 0.5\n")
        f.flush()
        errors = validate_eval_contract(Path(f.name))
    assert errors == []


def test_missing_function():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def helper():\n    pass\n")
        f.flush()
        errors = validate_eval_contract(Path(f.name))
    assert len(errors) == 1
    assert "evaluate" in errors[0] or "score" in errors[0]


def test_missing_file():
    errors = validate_eval_contract(Path("/nonexistent/eval.py"))
    assert len(errors) == 1
    assert "not found" in errors[0]


def test_syntax_error():
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def evaluate(\n")
        f.flush()
        errors = validate_eval_contract(Path(f.name))
    assert len(errors) == 1
    assert "syntax" in errors[0].lower()


def test_existing_task_evals():
    from srf.tasks.registry import TaskRegistry

    registry = TaskRegistry()
    for name in registry.names():
        raw = registry.get_raw(name)
        task_dir = Path(raw["_dir"])
        eval_path = task_dir / "eval.py"
        errors = validate_eval_contract(eval_path)
        assert errors == [], f"{name}/eval.py failed: {errors}"
