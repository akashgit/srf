"""CLI integration tests — the commands that inspect the package and emit its IR."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from srf.cli import main
from srf.graphs import MODES, SPINE_PROBE, SPINE_SOURCE, TSX_LOADER


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main(argv)
    return code, capsys.readouterr().out


def test_modes_lists_every_mode(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(["modes"], capsys)
    assert code == 0
    for mode in MODES:
        assert f"  - {mode}" in out


def test_tasks_lists_discovered_tasks(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(["tasks"], capsys)
    assert code == 0
    assert "circle_packing" in out


def test_tasks_filtered_by_category(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(["tasks", "--category", "gpu"], capsys)
    assert code == 0
    assert "trimul" in out
    assert "circle_packing" not in out


def test_graph_writes_one_mode_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(["graph", "--mode", "gepa"], capsys)
    assert code == 0
    payload = json.loads(out)
    assert payload["name"] == "gepa"
    assert payload["start_node"] == "task_input"


def test_graph_writes_to_a_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    destination = tmp_path / "gepa.graph.json"
    code, out = run(["graph", "--mode", "gepa", "--out", str(destination)], capsys)
    assert code == 0
    assert str(destination) in out
    assert json.loads(destination.read_text())["name"] == "gepa"


def test_graph_rejects_an_unknown_mode(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["graph", "--mode", "not_a_mode"])
    captured = capsys.readouterr()
    assert code == 1
    assert "not_a_mode" in captured.err


def test_graphs_emits_every_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(["graphs", "--out", str(tmp_path)], capsys)
    assert code == 0
    for mode in MODES:
        assert (tmp_path / f"{mode}.graph.json").exists()
    assert len(out.strip().splitlines()) == len(MODES)


def test_run_no_longer_executes_here(capsys: pytest.CaptureFixture[str]) -> None:
    """SRF declares graphs; the runtime is DSH. ``srf run`` must not pretend otherwise."""
    code = main(["run", "--mode", "gepa", "--task", "circle_packing"])
    captured = capsys.readouterr()
    assert code == 1
    assert "workflow spine" in captured.err
    assert "Phase 4" in captured.err


@pytest.mark.skipif(
    shutil.which("node") is None or not SPINE_SOURCE.exists() or not TSX_LOADER.exists(),
    reason="needs node and the DSH workflow-spine checkout",
)
def test_probe_command_walks_every_graph(tmp_path: Path) -> None:
    """The CLI path end to end: emit the graphs, then load them into the spine."""
    graphs = tmp_path / "graphs"
    assert main(["graphs", "--out", str(graphs)]) == 0
    completed = subprocess.run(
        [sys.executable, "-m", "srf.cli", "probe", "--graphs", str(graphs)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stdout[-2000:] + completed.stderr[-2000:]
    report = json.loads(completed.stdout)
    assert [entry["name"] for entry in report] == sorted(MODES)
    for entry in report:
        assert entry["ok"] is True, (entry["name"], entry["error"])
        assert entry["missed"] == []


def test_probe_requires_emitted_graphs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["probe", "--graphs", str(tmp_path / "empty")])
    captured = capsys.readouterr()
    assert code == 1
    assert "srf graphs" in captured.err


def test_probe_script_ships_with_the_package() -> None:
    """The probe is the boundary test, so it travels with the graphs it checks."""
    assert SPINE_PROBE.exists()
    assert SPINE_PROBE.parent.name == "tools"
