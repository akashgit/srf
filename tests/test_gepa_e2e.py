"""End-to-end test — run GEPA via CLI with mock LLM, validate full pipeline."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def test_cli_run_gepa_e2e():
    """Run the FULL pipeline: CLI -> registry -> mode -> Package execution -> ops -> sandbox -> trace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "run_output"

        mock_code = (
            "```python\n"
            "import math\n"
            "\n"
            "def solve(n: int, radii: list[float]) -> list[tuple[float, float]]:\n"
            "    centers = []\n"
            "    for i, r in enumerate(radii):\n"
            "        x = min(max(r, (i % 6) * 0.16 + 0.08), 1.0 - r)\n"
            "        y = min(max(r, (i // 6) * 0.2 + 0.1), 1.0 - r)\n"
            "        centers.append((x, y))\n"
            "    return centers\n"
            "```"
        )
        mock_file = Path(tmpdir) / "mock_responses.json"
        mock_file.write_text(json.dumps([mock_code] * 10))

        result = subprocess.run(
            [
                sys.executable, "-m", "srf.cli",
                "run",
                "--mode", "gepa",
                "--task", "circle_packing",
                "--budget", "3",
                "--mock-llm",
                "--mock-responses", str(mock_file),
                "--output-dir", str(output_dir),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

        stdout_lines = result.stdout.strip().split("\n")
        json_output = "\n".join(stdout_lines[-10:])
        run_result = None
        for i in range(len(stdout_lines)):
            try:
                run_result = json.loads("\n".join(stdout_lines[i:]))
                break
            except json.JSONDecodeError:
                continue
        assert run_result is not None, f"No JSON output found in:\n{result.stdout}"
        assert "run_id" in run_result
        assert run_result["mode"] == "gepa"
        assert run_result["task"] == "circle_packing"
        assert run_result["eval_count"] >= 1

        assert output_dir.exists(), "Output directory not created"
        assert (output_dir / "best_solution.py").exists(), "Missing best_solution.py"
        assert (output_dir / "evaluations.jsonl").exists(), "Missing evaluations.jsonl"
        assert (output_dir / "candidates.jsonl").exists(), "Missing candidates.jsonl"
        assert (output_dir / "llm_calls.jsonl").exists(), "Missing llm_calls.jsonl"
        assert (output_dir / "policy_decisions.jsonl").exists(), "Missing policy_decisions.jsonl"
        assert (output_dir / "budget.jsonl").exists(), "Missing budget.jsonl"

        evals = _read_jsonl(output_dir / "evaluations.jsonl")
        assert len(evals) >= 1, "No evaluations recorded"
        for e in evals:
            assert "score" in e
            assert "candidate_id" in e

        llm_calls = _read_jsonl(output_dir / "llm_calls.jsonl")
        assert len(llm_calls) >= 1, "No LLM calls recorded"
        for call in llm_calls:
            assert call["input_tokens"] > 0
            assert call["output_tokens"] > 0

        decisions = _read_jsonl(output_dir / "policy_decisions.jsonl")
        assert len(decisions) >= 1, "No policy decisions recorded"
        for d in decisions:
            assert d["decision"] in ("PROCEED", "RELOOP")

        state = json.loads((output_dir / "gepa_state.json").read_text())
        assert state["eval_count"] >= 1
        assert state["eval_count"] <= 5

        population = json.loads((output_dir / "population.json").read_text())
        assert len(population) >= 1

        budget_state = json.loads((output_dir / "budget_state.json").read_text())
        assert budget_state["llm_calls"] >= 1
        assert budget_state["llm_input_tokens"] > 0


def test_cli_modes_command():
    result = subprocess.run(
        [sys.executable, "-m", "srf.cli", "modes"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "gepa" in result.stdout


def test_cli_tasks_command():
    result = subprocess.run(
        [sys.executable, "-m", "srf.cli", "tasks"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "circle_packing" in result.stdout
    assert "autocorrelation_inequality" in result.stdout
    assert "trimul" in result.stdout


def test_cli_tasks_filter_category():
    result = subprocess.run(
        [sys.executable, "-m", "srf.cli", "tasks", "--category", "math"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert "circle_packing" in result.stdout
    assert "trimul" not in result.stdout


def test_cli_unknown_mode_error():
    result = subprocess.run(
        [sys.executable, "-m", "srf.cli", "run", "--mode", "nonexistent", "--task", "circle_packing", "--budget", "1", "--mock-llm"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert "unknown mode" in result.stderr.lower() or "unknown mode" in result.stdout.lower()


def test_cli_unknown_task_error():
    result = subprocess.run(
        [sys.executable, "-m", "srf.cli", "run", "--mode", "gepa", "--task", "nonexistent", "--budget", "1", "--mock-llm"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1


def test_merge_path_e2e():
    """Run with low stagnation threshold + lenient acceptance so merge triggers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "merge_test"

        result = subprocess.run(
            [
                sys.executable, "-m", "srf.cli",
                "run",
                "--mode", "gepa",
                "--task", "circle_packing",
                "--budget", "5",
                "--mock-llm",
                "--knob", "merge_stagnation_threshold=1",
                "--knob", "acceptance_mode=lenient",
                "--output-dir", str(output_dir),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, f"CLI failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

        decisions = _read_jsonl(output_dir / "policy_decisions.jsonl")
        merge_decisions = [d for d in decisions if d["decision"] == "RELOOP"]
        assert len(merge_decisions) >= 1, (
            f"Expected at least one RELOOP (merge) decision, got decisions: "
            f"{[d['decision'] for d in decisions]}"
        )

        state = json.loads((output_dir / "gepa_state.json").read_text())
        assert state["merge_attempts"] >= 1, f"merge_attempts should be >= 1, got {state['merge_attempts']}"

        candidates = _read_jsonl(output_dir / "candidates.jsonl")
        merge_candidates = [c for c in candidates if c.get("source") == "merge"]
        assert len(merge_candidates) >= 1, "Expected at least one candidate with source='merge'"

        assert (output_dir / "merge_candidates.json").exists(), "Missing merge_candidates.json"
        assert (output_dir / "best_solution.py").exists(), "Missing best_solution.py"


def test_knob_overrides():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "knob_test"
        result = subprocess.run(
            [
                sys.executable, "-m", "srf.cli",
                "run",
                "--mode", "gepa",
                "--task", "circle_packing",
                "--budget", "1",
                "--mock-llm",
                "--knob", "temperature=0.9",
                "--knob", "parent_selection=pareto",
                "--output-dir", str(output_dir),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        knobs = json.loads((output_dir / "knobs.json").read_text())
        assert knobs["temperature"] == 0.9
        assert knobs["parent_selection"] == "pareto"


class TestProviderAutoDetection:
    """Unit tests for _resolve_provider auto-detection logic (no API calls)."""

    def _make_args(self, mock_llm: bool = False, provider: str = "auto") -> argparse.Namespace:
        return argparse.Namespace(mock_llm=mock_llm, provider=provider, mock_responses=None)

    def test_mock_llm_flag_overrides_provider(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args(mock_llm=True)) == "mock"

    def test_explicit_provider_openai(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args(provider="openai")) == "openai"

    def test_explicit_provider_anthropic(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args(provider="anthropic")) == "anthropic"

    def test_auto_prefers_openai_over_anthropic(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args()) == "openai"

    def test_auto_falls_back_to_anthropic(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args()) == "anthropic"

    def test_explicit_provider_vertex(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args(provider="vertex")) == "vertex"

    def test_auto_vertex_when_project_id_set(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "my-gcp-project")
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args()) == "vertex"

    def test_auto_openai_preferred_over_vertex(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "my-gcp-project")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args()) == "openai"

    def test_auto_vertex_preferred_over_anthropic(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_VERTEX_PROJECT_ID", "my-gcp-project")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args()) == "vertex"

    def test_auto_no_keys_returns_none(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_VERTEX_PROJECT_ID", raising=False)
        from srf.cli import _resolve_provider
        assert _resolve_provider(self._make_args()) == "none"


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records
