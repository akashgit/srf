"""Benchmark comparison — score/cost/behavioral parity reporter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from srf.ops.common.trace_validator import validate_traces


def compare(
    srf_trace_dir: Path,
    flora_trace_dir: Path,
    task_name: str = "",
) -> dict[str, Any]:
    """Compare SRF run against Flora baseline.

    Returns:
      - score_parity: srf_score / flora_score >= 0.95
      - cost_parity: srf_tokens / flora_tokens <= 1.5
      - behavioral_fidelity: trace validator parity score
    """
    srf_stats = _load_run_stats(srf_trace_dir)
    flora_stats = _load_run_stats(flora_trace_dir)
    trace_report = validate_traces(flora_trace_dir, srf_trace_dir)

    srf_score = srf_stats.get("best_score", 0.0)
    flora_score = flora_stats.get("best_score", 1.0)
    score_ratio = srf_score / flora_score if flora_score > 0 else 0.0

    srf_tokens = srf_stats.get("total_tokens", 0)
    flora_tokens = flora_stats.get("total_tokens", 1)
    cost_ratio = srf_tokens / flora_tokens if flora_tokens > 0 else 0.0

    return {
        "task": task_name,
        "score_parity": {
            "srf_score": srf_score,
            "flora_score": flora_score,
            "ratio": round(score_ratio, 4),
            "pass": score_ratio >= 0.95,
        },
        "cost_parity": {
            "srf_tokens": srf_tokens,
            "flora_tokens": flora_tokens,
            "ratio": round(cost_ratio, 4),
            "pass": cost_ratio <= 1.5,
        },
        "behavioral_fidelity": {
            "parity_score": trace_report.get("parity_score", 0.0),
            "anomalies": len(trace_report.get("anomalies", [])),
        },
        "overall_pass": score_ratio >= 0.95 and cost_ratio <= 1.5,
    }


def _load_run_stats(trace_dir: Path) -> dict[str, Any]:
    stats: dict[str, Any] = {"best_score": 0.0, "total_tokens": 0}

    evals_path = trace_dir / "evaluations.jsonl"
    if evals_path.exists():
        scores = []
        for line in evals_path.read_text().splitlines():
            if line.strip():
                try:
                    scores.append(json.loads(line).get("score", 0.0))
                except json.JSONDecodeError:
                    continue
        if scores:
            stats["best_score"] = max(scores)

    llm_path = trace_dir / "llm_calls.jsonl"
    if llm_path.exists():
        total = 0
        for line in llm_path.read_text().splitlines():
            if line.strip():
                try:
                    record = json.loads(line)
                    total += record.get("input_tokens", 0) + record.get("output_tokens", 0)
                except json.JSONDecodeError:
                    continue
        stats["total_tokens"] = total

    return stats


def generate_report(comparison: dict[str, Any]) -> str:
    """Generate human-readable markdown comparison report."""
    lines = [
        f"# Benchmark Comparison: {comparison.get('task', 'unknown')}",
        "",
        "## Score Parity",
        f"- SRF: {comparison['score_parity']['srf_score']:.4f}",
        f"- Flora: {comparison['score_parity']['flora_score']:.4f}",
        f"- Ratio: {comparison['score_parity']['ratio']:.4f} (>= 0.95 required)",
        f"- **{'PASS' if comparison['score_parity']['pass'] else 'FAIL'}**",
        "",
        "## Cost Parity",
        f"- SRF tokens: {comparison['cost_parity']['srf_tokens']}",
        f"- Flora tokens: {comparison['cost_parity']['flora_tokens']}",
        f"- Ratio: {comparison['cost_parity']['ratio']:.4f} (<= 1.5 required)",
        f"- **{'PASS' if comparison['cost_parity']['pass'] else 'FAIL'}**",
        "",
        "## Behavioral Fidelity",
        f"- Parity score: {comparison['behavioral_fidelity']['parity_score']:.4f}",
        f"- Anomalies: {comparison['behavioral_fidelity']['anomalies']}",
        "",
        f"## Overall: **{'PASS' if comparison['overall_pass'] else 'FAIL'}**",
    ]
    return "\n".join(lines)
