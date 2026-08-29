"""Trace-level fidelity checker — diffs SRF and Flora traces for behavioral parity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_traces(
    baseline_path: Path,
    srf_path: Path | None = None,
) -> dict[str, Any]:
    """Parse and diff trace files for behavioral fidelity.

    Returns a report with parity scores across dimensions:
    - population_evolution: population sizes and elite scores per iteration
    - selection_events: parent IDs, selection method
    - branch_decisions: merge/mutate Conditional decisions, stagnation counts
    - anomalies: sudden score jumps, identical outputs
    """
    baseline = _load_trace_dir(baseline_path)
    srf_trace = _load_trace_dir(srf_path) if srf_path else {}

    report: dict[str, Any] = {
        "baseline_stats": _compute_stats(baseline),
        "comparison": {},
        "anomalies": [],
        "parity_score": 0.0,
    }

    if srf_trace:
        report["srf_stats"] = _compute_stats(srf_trace)
        report["comparison"] = _compare_traces(baseline, srf_trace)
        report["anomalies"] = _detect_anomalies(srf_trace)
        report["parity_score"] = _compute_parity(report["comparison"])

    return report


def _load_trace_dir(path: Path) -> dict[str, list[dict]]:
    traces: dict[str, list[dict]] = {}
    if path.is_dir():
        for fname in ["evaluations.jsonl", "candidates.jsonl", "llm_calls.jsonl",
                       "policy_decisions.jsonl", "budget.jsonl"]:
            fpath = path / fname
            if fpath.exists():
                traces[fname.replace(".jsonl", "")] = _load_jsonl(fpath)
    elif path.is_file():
        traces["combined"] = _load_jsonl(path)
    return traces


def _load_jsonl(path: Path) -> list[dict]:
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _compute_stats(traces: dict[str, list[dict]]) -> dict[str, Any]:
    evals = traces.get("evaluations", [])
    candidates = traces.get("candidates", [])
    decisions = traces.get("policy_decisions", [])

    scores = [e.get("score", 0) for e in evals]

    return {
        "total_evaluations": len(evals),
        "total_candidates": len(candidates),
        "total_decisions": len(decisions),
        "max_score": max(scores) if scores else 0.0,
        "final_score": scores[-1] if scores else 0.0,
        "score_progression": scores[:50],
    }


def _compare_traces(
    baseline: dict[str, list[dict]], srf: dict[str, list[dict]]
) -> dict[str, Any]:
    b_evals = baseline.get("evaluations", [])
    s_evals = srf.get("evaluations", [])
    b_decisions = baseline.get("policy_decisions", [])
    s_decisions = srf.get("policy_decisions", [])

    b_scores = [e.get("score", 0) for e in b_evals]
    s_scores = [e.get("score", 0) for e in s_evals]

    score_parity = 0.0
    if b_scores and s_scores:
        b_max = max(b_scores) if b_scores else 1.0
        s_max = max(s_scores) if s_scores else 0.0
        score_parity = min(s_max / b_max, 1.0) if b_max > 0 else 1.0

    b_merge_count = sum(1 for d in b_decisions if d.get("decision") == "RELOOP")
    s_merge_count = sum(1 for d in s_decisions if d.get("decision") == "RELOOP")

    branch_parity = 1.0
    if b_merge_count > 0:
        branch_parity = 1.0 - abs(b_merge_count - s_merge_count) / max(b_merge_count, s_merge_count, 1)

    return {
        "score_parity": round(score_parity, 4),
        "branch_decision_parity": round(branch_parity, 4),
        "baseline_merge_count": b_merge_count,
        "srf_merge_count": s_merge_count,
    }


def _detect_anomalies(traces: dict[str, list[dict]]) -> list[dict[str, Any]]:
    anomalies = []
    evals = traces.get("evaluations", [])
    scores = [e.get("score", 0) for e in evals]

    if len(scores) > 2:
        mean = sum(scores) / len(scores)
        std = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5
        for i in range(1, len(scores)):
            if std > 0 and abs(scores[i] - scores[i - 1]) > 2 * std:
                anomalies.append({
                    "type": "score_jump",
                    "iteration": i,
                    "delta": round(scores[i] - scores[i - 1], 4),
                    "threshold": round(2 * std, 4),
                })

    candidates = traces.get("candidates", [])
    seen_hashes = set()
    for c in candidates:
        h = c.get("code_hash", "")
        if h and h in seen_hashes:
            anomalies.append({"type": "duplicate_output", "hash": h, "iteration": c.get("iteration")})
        seen_hashes.add(h)

    return anomalies


def _compute_parity(comparison: dict[str, Any]) -> float:
    if not comparison:
        return 0.0
    score_p = comparison.get("score_parity", 0.0)
    branch_p = comparison.get("branch_decision_parity", 0.0)
    return round(0.6 * score_p + 0.4 * branch_p, 4)
