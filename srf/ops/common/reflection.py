"""Reflection analysis — meta-scratchpad for evolutionary modes."""

from __future__ import annotations

from typing import Any

import structlog

from srf.ops.common.prompts import format_task_header

logger = structlog.get_logger()


def build_reflection_prompt(task: dict[str, Any], recent_history: list[dict[str, Any]],
                            max_entries: int = 10) -> str:
    """Build a reflection prompt from recent evaluation history."""
    parts = [format_task_header(task)]
    parts.append("## Recent Evolution History")

    for entry in recent_history[-max_entries:]:
        score = entry.get("score", 0.0)
        action = entry.get("action", "mutate")
        improved = entry.get("improved", False)
        parts.append(f"- {action}: score={score:.4f} {'(improved)' if improved else '(no improvement)'}")

    parts.append(
        "\n## Instructions\n"
        "Analyze the evolution history above. Identify:\n"
        "1. Which mutation strategies are working\n"
        "2. Which strategies are not working\n"
        "3. Suggestions for the next mutation to try\n"
        "Be specific and actionable."
    )
    return "\n\n".join(parts)


def analyze_stagnation(history: list[dict[str, Any]], window: int = 10) -> dict[str, Any]:
    """Analyze if the population is stagnating."""
    if len(history) < window:
        return {"stagnating": False, "reason": "insufficient_history"}

    recent = history[-window:]
    improvements = sum(1 for h in recent if h.get("improved", False))
    scores = [h.get("score", 0.0) for h in recent]
    score_range = max(scores) - min(scores) if scores else 0.0

    stagnating = improvements == 0 or score_range < 0.001
    return {
        "stagnating": stagnating,
        "improvements_in_window": improvements,
        "score_range": score_range,
        "reason": "no_improvements" if improvements == 0 else "low_diversity" if score_range < 0.001 else "ok",
    }
