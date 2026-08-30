"""AIDE mode — tree search (draft/improve/debug).

DAG structure:
  Loop(body=Sequential(
    search_policy,
    Conditional(gate, {DRAFT: draft_pkg, IMPROVE: improve_pkg, DEBUG: debug_pkg}),
    eval_pkg,
    tree_update
  ), gate=budget)
"""

from __future__ import annotations

from srf._factory_shim import (
    Conditional,
    Edge,
    FnNode,
    GateNode,
    LLMNode,
    Loop,
    MemoryDeclaration,
    OptKnob,
    Package,
    Sequential,
    Workflow,
)

SYSTEM_PROMPT_DRAFT = (
    "You are AIDE, a code optimization agent using tree search. "
    "Generate a new solution from scratch for the given task. "
    "Output a single fenced code block."
)

SYSTEM_PROMPT_IMPROVE = (
    "You are AIDE. Improve the best solution found so far. "
    "Build on what works and enhance performance. "
    "Output a single fenced code block."
)

SYSTEM_PROMPT_DEBUG = (
    "You are AIDE. Fix the bugs in the given solution. "
    "The code has errors — analyze the output and produce a working version. "
    "Output a single fenced code block."
)


def build_aide_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.7,
                bounds=[0.3, 0.5, 0.7, 0.9], node_id="generate",
                description="LLM sampling temperature"),
        OptKnob(name="debug_prob", kind="threshold", default=0.3,
                bounds=[0.1, 0.2, 0.3, 0.5], node_id="search_policy",
                description="Probability of debugging a buggy node"),
        OptKnob(name="max_tree_depth", kind="threshold", default=10.0,
                bounds=[5.0, 10.0, 20.0], node_id="tree_update",
                description="Maximum tree depth"),
    ]


def build_aide_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="aide.tree", kind="kv", retention="run"),
        MemoryDeclaration(namespace="aide.actions", kind="log", retention="run"),
    ]


def _build_action_gate() -> GateNode:
    return GateNode(
        name="action_gate",
        evaluator_command="python -m srf.ops.aide.gate action",
    )


def build_aide_workflow() -> Workflow:
    policy = FnNode(
        name="search_policy",
        callable_name="srf.ops.aide.ops:search_policy",
        reads={"tree_state.json"},
        writes={"aide_action.txt", "aide_target.json"},
    )

    draft_prompt = FnNode(
        name="build_draft_prompt",
        callable_name="srf.ops.aide.ops:build_draft_prompt",
        reads={"task.yaml"},
        writes={"aide_prompt.md"},
    )
    draft_gen = LLMNode(
        name="draft_generate",
        model="sonnet", temperature=0.7,
        system_prompt=SYSTEM_PROMPT_DRAFT,
        reads={"aide_prompt.md"}, writes={"candidate.py"},
    )
    draft_pkg = Package(
        name="aide-draft",
        nodes=[draft_prompt, draft_gen],
        edges=[Edge(source="build_draft_prompt", target="draft_generate")],
    )

    improve_prompt = FnNode(
        name="build_improve_prompt",
        callable_name="srf.ops.aide.ops:build_improve_prompt",
        reads={"tree_state.json", "aide_target.json", "task.yaml"},
        writes={"aide_prompt.md"},
    )
    improve_gen = LLMNode(
        name="improve_generate",
        model="sonnet", temperature=0.7,
        system_prompt=SYSTEM_PROMPT_IMPROVE,
        reads={"aide_prompt.md"}, writes={"candidate.py"},
    )
    improve_pkg = Package(
        name="aide-improve",
        nodes=[improve_prompt, improve_gen],
        edges=[Edge(source="build_improve_prompt", target="improve_generate")],
    )

    debug_prompt = FnNode(
        name="build_debug_prompt",
        callable_name="srf.ops.aide.ops:build_debug_prompt",
        reads={"tree_state.json", "aide_target.json", "task.yaml"},
        writes={"aide_prompt.md"},
    )
    debug_gen = LLMNode(
        name="debug_generate",
        model="sonnet", temperature=0.5,
        system_prompt=SYSTEM_PROMPT_DEBUG,
        reads={"aide_prompt.md"}, writes={"candidate.py"},
    )
    debug_pkg = Package(
        name="aide-debug",
        nodes=[debug_prompt, debug_gen],
        edges=[Edge(source="build_debug_prompt", target="debug_generate")],
    )

    action_cond = Conditional(
        name="aide-action",
        gate=_build_action_gate(),
        branches={"DRAFT": draft_pkg, "IMPROVE": improve_pkg, "DEBUG": debug_pkg},
    )

    evaluate = FnNode(
        name="sandbox_eval",
        callable_name="srf.ops.common.sandbox:run_eval",
        reads={"candidate.py", "task.yaml"},
        writes={"eval_result.json"},
    )

    tree_update = FnNode(
        name="tree_update",
        callable_name="srf.ops.aide.ops:update_tree",
        reads={"eval_result.json", "candidate.py", "aide_target.json", "tree_state.json"},
        writes={"tree_state.json", "aide_state.json", "best_solution.py"},
    )

    budget_gate = GateNode(
        name="budget_check",
        evaluator_command="python -m srf.ops.common.budget check",
    )

    iteration = Sequential(
        name="aide-iteration",
        children=[policy, action_cond, evaluate, tree_update],
    )

    aide_loop = Loop(
        name="aide",
        body=iteration,
        gate=budget_gate,
        max_iterations=500,
    )

    return Workflow(
        name="aide",
        root=aide_loop,
        knobs=build_aide_knobs(),
        memory=build_aide_memory(),
    )
