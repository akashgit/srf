"""AIDE domain operations — search policy, draft/improve/debug prompts, tree update."""

from __future__ import annotations

import hashlib
import random
from typing import Any

import structlog

from srf.ops.common.prompts import format_instructions, format_program_context, format_task_header
from srf.ops.common.tree import TreeNode, TreeState, summarize_path

logger = structlog.get_logger()


def search_policy(ctx: Any) -> None:
    """Decide action: DRAFT, IMPROVE, or DEBUG."""
    tree_state = _load_tree(ctx)
    debug_prob = float(ctx.knobs.get("debug_prob", 0.3))

    if not tree_state.nodes:
        ctx.write_text("aide_action.txt", "DRAFT")
        ctx.write_json("aide_target.json", {"action": "DRAFT", "target_id": None})
        return

    buggy = tree_state.get_buggy_nodes()
    if buggy and random.random() < debug_prob:
        target = random.choice(buggy)
        ctx.write_text("aide_action.txt", "DEBUG")
        ctx.write_json("aide_target.json", {"action": "DEBUG", "target_id": target.id})
        return

    best = tree_state.get_best()
    if best:
        ctx.write_text("aide_action.txt", "IMPROVE")
        ctx.write_json("aide_target.json", {"action": "IMPROVE", "target_id": best.id})
    else:
        ctx.write_text("aide_action.txt", "DRAFT")
        ctx.write_json("aide_target.json", {"action": "DRAFT", "target_id": None})


def build_draft_prompt(ctx: Any) -> None:
    task = ctx.task
    parts = [
        format_task_header(task),
        format_program_context(task.get("initial_code", ""), label="Initial Code"),
        format_instructions("aide"),
    ]
    ctx.write_text("aide_prompt.md", "\n\n".join(parts))


def build_improve_prompt(ctx: Any) -> None:
    task = ctx.task
    tree_state = _load_tree(ctx)
    target = ctx.read_json("aide_target.json") or {}
    target_id = target.get("target_id")

    parts = [format_task_header(task)]
    if target_id and target_id in tree_state.nodes:
        path_summary = summarize_path(tree_state, target_id)
        node = tree_state.nodes[target_id]
        parts.append(format_program_context(node.code, node.score, "Current Best"))
        parts.append(f"## Search Path Summary\n{path_summary}")
    parts.append(
        "## Instructions\nImprove the solution above. "
        "Build on what works, fix what doesn't. "
        "Output a single fenced code block."
    )
    ctx.write_text("aide_prompt.md", "\n\n".join(parts))


def build_debug_prompt(ctx: Any) -> None:
    task = ctx.task
    tree_state = _load_tree(ctx)
    target = ctx.read_json("aide_target.json") or {}
    target_id = target.get("target_id")

    parts = [format_task_header(task)]
    if target_id and target_id in tree_state.nodes:
        node = tree_state.nodes[target_id]
        parts.append(format_program_context(node.code, node.score, "Buggy Solution"))
        if node.terminal_output:
            parts.append(f"## Error Output\n```\n{node.terminal_output[:500]}\n```")
    parts.append(
        "## Instructions\nFix the bugs in the solution above. "
        "The code has errors — debug and produce a working version. "
        "Output a single fenced code block."
    )
    ctx.write_text("aide_prompt.md", "\n\n".join(parts))


def update_tree(ctx: Any) -> None:
    """Add evaluation result to tree state."""
    tree_state = _load_tree(ctx)
    eval_result = ctx.read_json("eval_result.json") or {}
    candidate_code = ctx.read_text("candidate.py")
    target = ctx.read_json("aide_target.json") or {}

    child_id = hashlib.sha256(candidate_code.encode()).hexdigest()[:12]
    score = eval_result.get("score", 0.0)
    error = eval_result.get("error")
    action = target.get("action", "DRAFT")
    parent_id = target.get("target_id")

    node = TreeNode(
        id=child_id,
        code=candidate_code,
        score=score,
        is_buggy=error is not None,
        parent_id=parent_id,
        terminal_output=error or eval_result.get("stdout", ""),
        metrics=eval_result.get("metrics", {}),
        action=action.lower(),
    )

    is_new_best = tree_state.add_node(node)
    if is_new_best:
        ctx.write_text("best_solution.py", candidate_code)
        logger.info("aide.new_best", score=score, id=child_id, action=action)

    tree_state.save(ctx.work_dir / "tree_state.json")

    state = ctx.read_json("aide_state.json") or {"eval_count": 0, "best_score": 0.0}
    state["eval_count"] = state.get("eval_count", 0) + 1
    state["best_score"] = tree_state.best_score
    state["best_id"] = tree_state.best_id
    ctx.write_json("aide_state.json", state)


def init_aide_state(ctx: Any) -> None:
    tree_state = TreeState()
    tree_state.save(ctx.work_dir / "tree_state.json")
    ctx.write_json("aide_state.json", {"eval_count": 0, "best_score": 0.0, "best_id": None})
    ctx.write_text("best_solution.py", ctx.task.get("initial_code", ""))


def _load_tree(ctx: Any) -> TreeState:
    return TreeState.load(ctx.work_dir / "tree_state.json")
