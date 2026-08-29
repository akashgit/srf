"""Budget tracking — LLM token cost and eval count.

Used as GateNode evaluator: python -m srf.ops.common.budget check
Tracks API-returned token counts (never client-side estimates).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

BUDGET_STATE_FILE = "budget_state.json"


def _default_budget_state() -> dict[str, Any]:
    return {
        "eval_count": 0,
        "llm_input_tokens": 0,
        "llm_output_tokens": 0,
        "llm_calls": 0,
        "budget_limit": 50,
    }


def init_budget(ctx: Any) -> None:
    state = _default_budget_state()
    state["budget_limit"] = ctx.budget_limit
    ctx.write_json(BUDGET_STATE_FILE, state)


def record_eval(ctx: Any) -> None:
    state = ctx.read_json(BUDGET_STATE_FILE) or _default_budget_state()
    state["eval_count"] += 1
    ctx.write_json(BUDGET_STATE_FILE, state)

    from srf.ops.common.tracing import log_budget
    log_budget(ctx, state["eval_count"], state["llm_input_tokens"], state["budget_limit"])

    logger.info("budget.record_eval", eval_count=state["eval_count"])


def record_llm_call(ctx: Any, input_tokens: int, output_tokens: int) -> None:
    state = ctx.read_json(BUDGET_STATE_FILE) or _default_budget_state()
    state["llm_input_tokens"] += input_tokens
    state["llm_output_tokens"] += output_tokens
    state["llm_calls"] += 1
    ctx.write_json(BUDGET_STATE_FILE, state)
    logger.info(
        "budget.record_llm",
        llm_calls=state["llm_calls"],
        total_input_tokens=state["llm_input_tokens"],
        total_output_tokens=state["llm_output_tokens"],
    )


def check() -> None:
    """GateNode evaluator — prints RELOOP (continue) or PROCEED (done)."""
    work_dir = Path(os.environ.get("SRF_WORK_DIR", "."))
    budget_path = work_dir / BUDGET_STATE_FILE
    if not budget_path.exists():
        print("RELOOP")
        return
    state = json.loads(budget_path.read_text())
    budget_limit = state.get("budget_limit", 50)
    eval_count = state.get("eval_count", 0)
    if eval_count >= budget_limit:
        logger.info("budget.exhausted", eval_count=eval_count, limit=budget_limit)
        print("PROCEED")
    else:
        print("RELOOP")


import os

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check()
    else:
        print(f"Usage: python -m srf.ops.common.budget check", file=sys.stderr)
        sys.exit(1)
