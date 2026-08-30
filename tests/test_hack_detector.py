"""Tests for hack detection (Issue #8)."""

from srf.ops.common.hack_detect import HackSignals, analyze_code, check_candidate


def test_clean_code_all_zero():
    code = """
import math

def solve(n):
    result = []
    for i in range(n):
        result.append(math.sqrt(i))
    return result
"""
    signals = analyze_code(code)
    assert signals.hardcoded_output == 0.0
    assert signals.forbidden_imports == 0.0
    assert signals.file_io == 0.0
    assert signals.monkey_patching == 0.0
    assert signals.test_data_access == 0.0
    assert signals.composite_score == 0.0


def test_detect_hardcoded_output():
    code = "def solve():\n    return 0.95\n"
    signals = analyze_code(code)
    assert signals.hardcoded_output > 0


def test_detect_forbidden_import_os():
    code = "import os\ndef solve():\n    return os.listdir('.')\n"
    signals = analyze_code(code)
    assert signals.forbidden_imports > 0


def test_detect_forbidden_import_subprocess():
    code = "import subprocess\ndef solve():\n    pass\n"
    signals = analyze_code(code)
    assert signals.forbidden_imports > 0


def test_detect_file_io_open():
    code = "def solve():\n    f = open('data.txt')\n    return f.read()\n"
    signals = analyze_code(code)
    assert signals.file_io > 0


def test_detect_monkey_patching_sys_modules():
    code = "import sys\nsys.modules['test'] = None\n"
    signals = analyze_code(code)
    assert signals.monkey_patching > 0


def test_detect_monkey_patching_builtins():
    code = "import builtins\nbuiltins.__import__ = lambda *a: None\n"
    signals = analyze_code(code)
    assert signals.monkey_patching > 0


def test_check_candidate_clean():
    code = "def solve(x):\n    return x * 2\n"
    is_clean, signals = check_candidate(code)
    assert is_clean is True
    assert signals.composite_score <= 0.3


def test_check_candidate_suspicious():
    code = """
import os
import subprocess
def solve():
    f = open('eval.py')
    return 0.99
"""
    is_clean, signals = check_candidate(code)
    assert is_clean is False
    assert signals.composite_score > 0.3


def test_syntax_error_graceful():
    code = "def broken(\n"
    signals = analyze_code(code)
    assert signals.composite_score == 0.0


def test_composite_score_weighted():
    signals = HackSignals(
        hardcoded_output=1.0,
        forbidden_imports=1.0,
        file_io=1.0,
        monkey_patching=1.0,
        test_data_access=1.0,
    )
    assert signals.composite_score == 1.0


def test_return_0_and_1_not_flagged():
    code = "def solve():\n    if True:\n        return 0\n    return 1\n"
    signals = analyze_code(code)
    assert signals.hardcoded_output == 0.0


def test_signals_to_dict():
    signals = HackSignals(hardcoded_output=0.5)
    d = signals.to_dict()
    assert "hardcoded_output" in d
    assert "composite_score" in d
    assert d["hardcoded_output"] == 0.5
