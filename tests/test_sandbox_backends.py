"""Tests for sandbox backend abstraction (Issue #3)."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from srf.ops.common.sandbox import (
    EvalResult,
    _execute_in_sandbox,
    _has_firejail,
    _has_gvisor,
    _run_gvisor,
    _run_subprocess,
)


def test_backend_auto_default():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "eval.py").write_text("import json; print(json.dumps({'score': 0.5}))")
    (tmp / "candidate.py").write_text("x = 1")
    result = _execute_in_sandbox(tmp, "python eval.py", 10, backend="auto")
    assert isinstance(result, EvalResult)


def test_backend_none():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "eval.py").write_text("import json; print(json.dumps({'score': 0.5}))")
    (tmp / "candidate.py").write_text("x = 1")
    result = _execute_in_sandbox(tmp, "python eval.py", 10, backend="none")
    assert isinstance(result, EvalResult)
    assert result.score == 0.5


def test_backend_subprocess():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "eval.py").write_text("import json; print(json.dumps({'score': 0.7}))")
    result = _run_subprocess(tmp, "python eval.py", 10)
    assert result.score == 0.7


def test_gvisor_fallback_when_not_installed():
    tmp = Path(tempfile.mkdtemp())
    (tmp / "eval.py").write_text("import json; print(json.dumps({'score': 0.3}))")
    with patch("srf.ops.common.sandbox._has_gvisor", return_value=False):
        result = _run_gvisor(tmp, "python eval.py", 10)
    assert isinstance(result, EvalResult)


def test_has_gvisor_returns_bool():
    result = _has_gvisor()
    assert isinstance(result, bool)


def test_has_firejail_returns_bool():
    result = _has_firejail()
    assert isinstance(result, bool)


def test_backend_parameter_accepted():
    for backend in ("auto", "firejail", "gvisor", "none"):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "eval.py").write_text("import json; print(json.dumps({'score': 0.1}))")
        (tmp / "candidate.py").write_text("x = 1")
        # Should not crash for any backend value
        result = _execute_in_sandbox(tmp, "python eval.py", 10, backend=backend)
        assert isinstance(result, EvalResult)


def test_eval_result_dataclass():
    r = EvalResult(score=0.5, metrics={"acc": 0.9}, error=None)
    assert r.score == 0.5
    assert r.metrics["acc"] == 0.9
    assert r.error is None
