"""Tests for trace-level fidelity validation."""

import json
import tempfile
from pathlib import Path

from srf.ops.common.trace_validator import validate_traces


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_validate_single_trace():
    with tempfile.TemporaryDirectory() as tmpdir:
        trace_dir = Path(tmpdir)
        _write_jsonl(trace_dir / "evaluations.jsonl", [
            {"score": 0.1, "iteration": 0},
            {"score": 0.3, "iteration": 1},
            {"score": 0.5, "iteration": 2},
        ])
        _write_jsonl(trace_dir / "candidates.jsonl", [
            {"candidate_id": "a", "code_hash": "abc"},
            {"candidate_id": "b", "code_hash": "def"},
        ])
        _write_jsonl(trace_dir / "policy_decisions.jsonl", [
            {"decision": "PROCEED", "reason": "no stagnation"},
        ])

        report = validate_traces(trace_dir)
        assert report["baseline_stats"]["total_evaluations"] == 3
        assert report["baseline_stats"]["max_score"] == 0.5


def test_validate_two_traces():
    with tempfile.TemporaryDirectory() as base_dir, tempfile.TemporaryDirectory() as srf_dir:
        base = Path(base_dir)
        srf = Path(srf_dir)

        _write_jsonl(base / "evaluations.jsonl", [
            {"score": 0.5, "iteration": 0},
            {"score": 0.8, "iteration": 1},
        ])
        _write_jsonl(base / "policy_decisions.jsonl", [
            {"decision": "PROCEED"},
            {"decision": "RELOOP"},
        ])

        _write_jsonl(srf / "evaluations.jsonl", [
            {"score": 0.4, "iteration": 0},
            {"score": 0.75, "iteration": 1},
        ])
        _write_jsonl(srf / "policy_decisions.jsonl", [
            {"decision": "PROCEED"},
            {"decision": "RELOOP"},
        ])

        report = validate_traces(base, srf)
        assert report["parity_score"] > 0
        assert report["comparison"]["score_parity"] > 0.5


def test_detect_duplicate_anomaly():
    with tempfile.TemporaryDirectory() as tmpdir:
        trace_dir = Path(tmpdir)
        _write_jsonl(trace_dir / "evaluations.jsonl", [{"score": 0.5}])
        _write_jsonl(trace_dir / "candidates.jsonl", [
            {"code_hash": "abc", "iteration": 0},
            {"code_hash": "abc", "iteration": 1},
        ])
        _write_jsonl(trace_dir / "policy_decisions.jsonl", [])

        report = validate_traces(trace_dir, trace_dir)
        anomalies = report.get("anomalies", [])
        dup_anomalies = [a for a in anomalies if a["type"] == "duplicate_output"]
        assert len(dup_anomalies) > 0
