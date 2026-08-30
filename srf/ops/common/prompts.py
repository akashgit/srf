"""Shared prompt formatting utilities used by all modes."""

from __future__ import annotations

from typing import Any


def format_task_header(task: dict[str, Any]) -> str:
    return (
        f"# Task: {task.get('name', 'unknown')}\n"
        f"Category: {task.get('category', '')}\n\n"
        f"{task.get('description', '')}"
    )


def format_program_context(code: str, score: float | None = None, label: str = "Current Solution") -> str:
    header = f"## {label}"
    if score is not None:
        header += f" (score: {score:.4f})"
    return f"{header}\n```python\n{code}\n```"


def format_eval_feedback(eval_result: dict[str, Any]) -> str:
    parts = [f"## Evaluation Result"]
    parts.append(f"Score: {eval_result.get('score', 0.0):.4f}")
    if eval_result.get("error"):
        parts.append(f"Error: {eval_result['error']}")
    metrics = eval_result.get("metrics", {})
    if metrics:
        parts.append("Metrics:")
        for k, v in metrics.items():
            parts.append(f"  - {k}: {v}")
    return "\n".join(parts)


def format_error_trace(error: str | None, stderr: str = "") -> str:
    if not error and not stderr:
        return ""
    parts = ["## Error Trace"]
    if error:
        parts.append(f"Error: {error}")
    if stderr:
        parts.append(f"Stderr:\n```\n{stderr[:500]}\n```")
    return "\n".join(parts)


def format_instructions(mode: str = "general") -> str:
    return (
        "## Instructions\n"
        "Produce an improved version of the solution. "
        "Focus on improving the score metric. "
        "Output a single fenced code block with the complete solution."
    )
