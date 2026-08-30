"""Tests for import allowlist validation (Issue #1)."""

from srf.tasks.schema import check_import_allowlist


def test_clean_code_no_violations():
    code = "import math\ndef solve():\n    return math.sqrt(2)\n"
    violations = check_import_allowlist(code)
    assert violations == []


def test_detect_dunder_import():
    code = "x = __import__('os')\n"
    violations = check_import_allowlist(code)
    assert len(violations) == 1
    assert "__import__" in violations[0]


def test_detect_importlib():
    code = "import importlib\nm = importlib.import_module('os')\n"
    violations = check_import_allowlist(code)
    assert len(violations) == 1
    assert "importlib" in violations[0]


def test_detect_exec():
    code = "exec('import os')\n"
    violations = check_import_allowlist(code)
    assert len(violations) == 1
    assert "exec" in violations[0]


def test_detect_eval():
    code = "eval('__import__(\"os\")')\n"
    violations = check_import_allowlist(code)
    assert len(violations) == 1
    assert "eval" in violations[0]


def test_multiple_violations():
    code = "__import__('os')\nexec('x')\neval('y')\n"
    violations = check_import_allowlist(code)
    assert len(violations) == 3


def test_syntax_error_returns_empty():
    code = "def broken(\n"
    violations = check_import_allowlist(code)
    assert violations == []
