"""Prompt construction — build_reflective_prompt and build_merge_prompt."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


def build_reflective_prompt(ctx: Any) -> None:
    """Compose the reflective mutation prompt from parent + rejection history.

    Reads: selected_parent.json, rejection_history.json, accepted_history.json, task.yaml
    Writes: mutate_prompt.md
    """
    parent = ctx.read_json("selected_parent.json") or {}
    rejections = ctx.read_json("rejection_history.json") or []
    accepted = ctx.read_json("accepted_history.json") or []
    task = ctx.task

    max_rejection_ctx = int(ctx.knobs.get("max_rejection_context", 5))
    recent_rejections = rejections[-max_rejection_ctx:] if rejections else []

    prompt_parts = [
        f"# Task: {task.get('name', 'unknown')}",
        f"\n{task.get('description', '')}",
        f"\n## Current Best Solution (score: {parent.get('score', 0.0)})",
        f"\n```python\n{parent.get('code', '')}\n```",
    ]

    if parent.get("metrics"):
        prompt_parts.append(f"\n## Evaluation Metrics\n{_format_metrics(parent['metrics'])}")

    if accepted:
        recent_accepted = accepted[-3:]
        prompt_parts.append("\n## Recently Accepted Improvements")
        for entry in recent_accepted:
            prompt_parts.append(
                f"- Score {entry.get('score', 0.0)}: "
                f"improved from {entry.get('parent_score', 0.0)}"
            )

    if recent_rejections:
        prompt_parts.append(f"\n## Recent Rejected Attempts ({len(recent_rejections)} shown)")
        for i, rej in enumerate(recent_rejections, 1):
            prompt_parts.append(f"\n### Rejected attempt {i}")
            prompt_parts.append(f"Score: {rej.get('score', 0.0)} (parent: {rej.get('parent_score', 0.0)})")
            if rej.get("error"):
                prompt_parts.append(f"Error: {rej['error']}")
            prompt_parts.append(f"```python\n{rej.get('code', '')[:500]}\n```")

        patterns = _analyze_failure_patterns(recent_rejections)
        if patterns:
            prompt_parts.append(f"\n## Failure Pattern Analysis\n{patterns}")

    prompt_parts.append(
        "\n## Instructions\n"
        "Produce an improved version of the solution. "
        "Learn from the rejected attempts above — avoid repeating the same mistakes. "
        "Focus on improving the score metric. "
        "Output a single fenced code block with the complete solution."
    )

    prompt = "\n".join(prompt_parts)
    ctx.write_text("mutate_prompt.md", prompt)
    logger.info(
        "prompts.reflective_built",
        parent_score=parent.get("score", 0.0),
        rejection_count=len(recent_rejections),
    )


def build_merge_prompt(ctx: Any) -> None:
    """Build a merge prompt from 2-3 candidate programs.

    Reads: merge_candidates.json, task.yaml
    Writes: merge_prompt.md
    """
    candidates = ctx.read_json("merge_candidates.json") or []
    task = ctx.task

    prompt_parts = [
        f"# Task: {task.get('name', 'unknown')}",
        f"\n{task.get('description', '')}",
        "\n## Programs to Merge",
    ]

    for i, cand in enumerate(candidates, 1):
        prompt_parts.append(
            f"\n### Program {i} (score: {cand.get('score', 0.0)})\n"
            f"```python\n{cand.get('code', '')}\n```"
        )

    prompt_parts.append(
        "\n## Instructions\n"
        "Combine the strengths of the programs above into a single improved program. "
        "Identify what makes each program score well and merge those techniques. "
        "Output a single fenced code block with the complete merged solution."
    )

    prompt = "\n".join(prompt_parts)
    ctx.write_text("merge_prompt.md", prompt)
    logger.info("prompts.merge_built", candidate_count=len(candidates))


def _format_metrics(metrics: dict) -> str:
    lines = []
    for k, v in metrics.items():
        if isinstance(v, float):
            lines.append(f"- {k}: {v:.4f}")
        else:
            lines.append(f"- {k}: {v}")
    return "\n".join(lines)


def _analyze_failure_patterns(rejections: list[dict]) -> str:
    errors = [r.get("error", "") for r in rejections if r.get("error")]
    score_drops = [
        r for r in rejections
        if r.get("score", 0) < r.get("parent_score", 0)
    ]

    lines = []
    if errors:
        lines.append(f"- {len(errors)}/{len(rejections)} attempts had errors")
    if score_drops:
        lines.append(f"- {len(score_drops)}/{len(rejections)} scored lower than parent")
    if not errors and not score_drops:
        lines.append("- All attempts ran but didn't improve enough")
    return "\n".join(lines)
