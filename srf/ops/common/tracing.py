"""Flora-compatible 5-file JSONL trace emission."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

TRACE_FILES = [
    "evaluations.jsonl",
    "candidates.jsonl",
    "llm_calls.jsonl",
    "policy_decisions.jsonl",
    "budget.jsonl",
]


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def init_trace_dir(work_dir: Path) -> None:
    for fname in TRACE_FILES:
        (work_dir / fname).touch()


def log_evaluation(ctx: Any, candidate_id: str, score: float, metrics: dict[str, Any]) -> None:
    record = {
        "timestamp": time.time(),
        "iteration": ctx.iteration,
        "run_id": ctx.run_id,
        "candidate_id": candidate_id,
        "score": score,
        "metrics": metrics,
    }
    _append_jsonl(ctx.work_dir / "evaluations.jsonl", record)
    logger.info("trace.evaluation", candidate_id=candidate_id, score=score)


def log_candidate(
    ctx: Any, candidate_id: str, parent_id: str | None, source: str, code_hash: str
) -> None:
    record = {
        "timestamp": time.time(),
        "iteration": ctx.iteration,
        "run_id": ctx.run_id,
        "candidate_id": candidate_id,
        "parent_id": parent_id,
        "source": source,
        "code_hash": code_hash,
    }
    _append_jsonl(ctx.work_dir / "candidates.jsonl", record)


def log_llm_call(
    ctx: Any, node_name: str, model: str, input_tokens: int, output_tokens: int
) -> None:
    record = {
        "timestamp": time.time(),
        "iteration": ctx.iteration,
        "run_id": ctx.run_id,
        "node": node_name,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    _append_jsonl(ctx.work_dir / "llm_calls.jsonl", record)
    logger.info(
        "trace.llm_call",
        node=node_name,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def log_policy_decision(ctx: Any, decision: str, reason: str, details: dict[str, Any] | None = None) -> None:
    record = {
        "timestamp": time.time(),
        "iteration": ctx.iteration,
        "run_id": ctx.run_id,
        "decision": decision,
        "reason": reason,
        "details": details or {},
    }
    _append_jsonl(ctx.work_dir / "policy_decisions.jsonl", record)
    logger.info("trace.policy_decision", decision=decision, reason=reason)


def log_budget(ctx: Any, eval_count: int, llm_cost_tokens: int, budget_limit: int) -> None:
    record = {
        "timestamp": time.time(),
        "iteration": ctx.iteration,
        "run_id": ctx.run_id,
        "eval_count": eval_count,
        "llm_input_tokens": llm_cost_tokens,
        "budget_limit": budget_limit,
    }
    _append_jsonl(ctx.work_dir / "budget.jsonl", record)
