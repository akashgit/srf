"""Tests for the sandbox eval runner."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from srf.ops.common.sandbox import EvalResult, _parse_eval_output, run_eval


def _make_ctx(work_dir: Path, task: dict | None = None):
    ctx = MagicMock()
    ctx.work_dir = work_dir
    ctx.task = task or {
        "name": "test_task",
        "category": "test",
        "eval_command": "python eval.py",
        "timeout": 10,
    }
    ctx.iteration = 0

    stored = {}

    def write_json(name, data):
        stored[name] = data
        (work_dir / name).write_text(json.dumps(data))

    def read_json(name):
        p = work_dir / name
        if p.exists():
            return json.loads(p.read_text())
        return stored.get(name)

    ctx.write_json = write_json
    ctx.read_json = read_json
    return ctx


def test_parse_eval_output_valid():
    stdout = '{"score": 0.75, "metrics": {"coverage": 0.8}}\n'
    result = _parse_eval_output(stdout, "")
    assert result.score == 0.75
    assert result.metrics["coverage"] == 0.8
    assert result.error is None


def test_parse_eval_output_no_json():
    result = _parse_eval_output("some random output", "")
    assert result.error is not None
    assert result.score == 0.0


def test_parse_eval_output_multiline():
    stdout = "loading...\n{\"score\": 1.0, \"metrics\": {}}\n"
    result = _parse_eval_output(stdout, "")
    assert result.score == 1.0


def test_run_eval_missing_candidate():
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        ctx = _make_ctx(work_dir)
        run_eval(ctx)
        result = json.loads((work_dir / "eval_result.json").read_text())
        assert result["error"] == "candidate.py not found"


def test_run_eval_with_simple_candidate():
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        (work_dir / "candidate.py").write_text("x = 1 + 1\n")
        (work_dir / "eval.py").write_text(
            'import json\nprint(json.dumps({"score": 0.5, "metrics": {}}))\n'
        )
        ctx = _make_ctx(work_dir, {
            "name": "inline_test",
            "category": "test",
            "eval_command": "python eval.py",
            "timeout": 10,
            "_dir": tmpdir,
        })
        run_eval(ctx)
        result = json.loads((work_dir / "eval_result.json").read_text())
        assert result["score"] == 0.5
