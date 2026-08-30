"""Research context utilities — literature synthesis and context injection."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


def load_literature_context(ctx: Any) -> str:
    """Load pre-supplied literature context file."""
    context_path = ctx.work_dir / "literature_context.md"
    if context_path.exists():
        return context_path.read_text()
    return ""


def build_research_context(task: dict[str, Any], literature: str = "") -> str:
    """Build research context for optimization-informed generation."""
    parts = [
        f"## Research Context for: {task.get('name', 'unknown')}",
        f"Category: {task.get('category', '')}",
        f"Objective: {'Maximize' if task.get('maximize', True) else 'Minimize'} {task.get('metric', 'score')}",
    ]
    if literature:
        parts.append(f"\n## Literature Survey\n{literature[:2000]}")
    return "\n\n".join(parts)


def synthesize_approaches(task: dict[str, Any], research_output: str) -> str:
    """Extract actionable approaches from research output."""
    return f"## Synthesized Approaches for {task.get('name', 'unknown')}\n{research_output[:1500]}"
