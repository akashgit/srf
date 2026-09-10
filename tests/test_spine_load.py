"""Phase 1 test gate: each of the 13 ``graph.json`` files loads into the DSH spine.

The probe does not read the graph the way SRF built it — it reads the emitted
JSON, exactly as the runtime does, validates it, and then drives the real spine
to completion. A pass means the graph is executable, not merely serializable.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from srf.graphs import MODES, SPINE_PROBE, SPINE_SOURCE, TSX_LOADER, write_graphs

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not SPINE_SOURCE.exists() or not TSX_LOADER.exists(),
    reason="needs node and the DSH workflow-spine checkout",
)


def _run_probe(tmp_path: Path) -> list[dict]:
    paths = write_graphs(tmp_path)
    environment = {
        **os.environ,
        "SRF_SPINE_MODULE": SPINE_SOURCE.resolve().as_uri(),
        "SRF_GATE_LOOPS": "3",
    }
    completed = subprocess.run(
        [
            "node",
            "--import",
            TSX_LOADER.resolve().as_uri(),
            str(SPINE_PROBE),
            *[str(path) for path in paths],
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert completed.stdout, f"probe produced no output:\n{completed.stderr}"
    return json.loads(completed.stdout)


@pytest.fixture(scope="module")
def report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict]:
    directory = tmp_path_factory.mktemp("graphs")
    entries = _run_probe(directory)
    assert [entry["name"] for entry in entries] == sorted(MODES)
    return {entry["name"]: entry for entry in entries}


@pytest.mark.parametrize("mode", MODES)
def test_graph_validates_in_the_spine(report: dict[str, dict], mode: str) -> None:
    """The spine's own structural validation must find nothing to complain about."""
    assert report[mode]["issues"] == []


@pytest.mark.parametrize("mode", MODES)
def test_graph_walks_to_completion(report: dict[str, dict], mode: str) -> None:
    """Driving the spine with real verdicts must terminate, not stall."""
    entry = report[mode]
    assert entry["error"] is None, entry["error"]
    assert entry["ok"] is True, f"{mode} never reached `done`"


@pytest.mark.parametrize("mode", MODES)
def test_walk_reaches_every_node(report: dict[str, dict], mode: str) -> None:
    """Every declared node is reachable by the walk — including alternative branches."""
    assert report[mode]["missed"] == []


@pytest.mark.parametrize("mode", MODES)
def test_walk_actually_moves(report: dict[str, dict], mode: str) -> None:
    entry = report[mode]
    assert entry["steps"] > 0
    assert len(entry["reached"]) == entry["nodes"]


def test_probe_reports_every_mode(tmp_path: Path) -> None:
    entries = _run_probe(tmp_path)
    assert len(entries) == len(MODES)
    assert all(entry["ok"] for entry in entries), [
        (entry["name"], entry["error"], entry["missed"]) for entry in entries if not entry["ok"]
    ]
