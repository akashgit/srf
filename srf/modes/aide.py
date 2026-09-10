"""AIDE mode — tree search over draft / improve / debug actions.

Graph:
  task_input → seed_run → Loop(aide):
    search_policy → action_gate ──draft───▶ build_draft_prompt → draft_generate
                                ──improve─▶ build_improve_prompt → improve_generate
                                ──debug───▶ build_debug_prompt → debug_generate
                                             │
                                             ▼
                        join_aide-action → sandbox_eval → tree_update
                                             │
                                             ▼
                          budget_check ──reloop──▶ search_policy
                                        ──proceed─▶ exit_aide

``action_gate`` is a switch, not a rewind: all three outcomes continue the same
iteration along different branches and converge on the shared eval/update tail.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    Conditional,
    MemoryDeclaration,
    OptKnob,
    Package,
    Sequential,
    budget_gate,
    chain,
    compile_mode,
    declared,
    gate,
    knob,
    llm,
    loop,
    memory,
    op,
    port,
    seed_run,
    single,
    task_input,
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

KNOBS = [
    knob(
        "temperature",
        "threshold",
        0.7,
        [0.3, 0.5, 0.7, 0.9],
        "draft_generate",
        "LLM sampling temperature",
    ),
    knob(
        "debug_prob",
        "threshold",
        0.3,
        [0.1, 0.2, 0.3, 0.5],
        "search_policy",
        "Probability of debugging a buggy node",
    ),
    knob(
        "max_tree_depth",
        "threshold",
        10.0,
        [5.0, 10.0, 20.0],
        "tree_update",
        "Maximum tree depth",
    ),
]

SEEDS = ("aide_state.json", "tree_state.json")
"""The loop's first pass reads the tree and the run's eval counter."""

MEMORY = [
    memory("aide.tree", "kv", "run"),
    memory("aide.actions", "log", "run"),
]

UPDATE_WRITES = {"tree_state.json", "aide_state.json", "best_solution.py"}


def _policy_package() -> Package:
    """Choose the iteration's action — the switch that routes the branch."""
    return single(
        op(
            "search_policy",
            "srf.ops.aide.ops:search_policy",
            reads={"tree_state.json"},
            writes={"aide_action.txt", "aide_target.json"},
            notes="Score the tree and pick DRAFT, IMPROVE, or DEBUG.",
        ),
        inputs=[port("tree", "tree_state.json", "application/json")],
        outputs=[port("action", "aide_action.txt", "text/plain")],
        requires={"tree_state.json"},
        produces={"aide_action.txt", "aide_target.json"},
    )


def _draft_package() -> Package:
    """Branch one: draft a solution from the task's initial code."""
    build_prompt = op(
        "build_draft_prompt",
        "srf.ops.aide.ops:build_draft_prompt",
        reads={"task.yaml"},
        writes={"aide_prompt.md"},
        notes="Prompt with the task header and its initial code.",
    )
    generate = llm(
        "draft_generate",
        SYSTEM_PROMPT_DRAFT,
        model="sonnet",
        temperature=0.7,
        reads={"aide_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "aide-draft",
        [build_prompt, generate],
        inputs=[port("task", "task.yaml", "application/yaml")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"task.yaml"},
        produces={"candidate.py"},
    )


def _improve_package() -> Package:
    """Branch two: improve the best node the search has found."""
    build_prompt = op(
        "build_improve_prompt",
        "srf.ops.aide.ops:build_improve_prompt",
        reads={"tree_state.json", "aide_target.json", "task.yaml"},
        writes={"aide_prompt.md"},
        notes="Prompt with the target node's code and its search path.",
    )
    generate = llm(
        "improve_generate",
        SYSTEM_PROMPT_IMPROVE,
        model="sonnet",
        temperature=0.7,
        reads={"aide_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "aide-improve",
        [build_prompt, generate],
        inputs=[port("tree", "tree_state.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"tree_state.json", "aide_target.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _debug_package() -> Package:
    """Branch three: repair a buggy node, sampling cooler than draft/improve."""
    build_prompt = op(
        "build_debug_prompt",
        "srf.ops.aide.ops:build_debug_prompt",
        reads={"tree_state.json", "aide_target.json", "task.yaml"},
        writes={"aide_prompt.md"},
        notes="Prompt with the buggy node's code and its error output.",
    )
    generate = llm(
        "debug_generate",
        SYSTEM_PROMPT_DEBUG,
        model="sonnet",
        temperature=0.5,
        reads={"aide_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "aide-debug",
        [build_prompt, generate],
        inputs=[port("tree", "tree_state.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"tree_state.json", "aide_target.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _eval_package() -> Package:
    """Score whichever branch produced the candidate."""
    return single(
        op(
            "sandbox_eval",
            "srf.ops.common.sandbox:run_eval",
            reads={"candidate.py", "task.yaml"},
            writes={"eval_result.json"},
            notes="Run the task's eval command on the candidate and record the score.",
        ),
        inputs=[port("candidate", "candidate.py", "text/x-python")],
        outputs=[port("result", "eval_result.json", "application/json")],
        requires={"candidate.py", "task.yaml"},
        produces={"eval_result.json"},
    )


def _update_package() -> Package:
    """Fold the score into the tree — the node that advances `best_solution.py`."""
    return single(
        op(
            "tree_update",
            "srf.ops.aide.ops:update_tree",
            reads={"eval_result.json", "candidate.py", "aide_target.json", "tree_state.json"},
            writes=UPDATE_WRITES,
            notes="Add the candidate to the tree and promote it when it scores best.",
        ),
        inputs=[port("result", "eval_result.json", "application/json")],
        outputs=[port("tree", "tree_state.json", "application/json")],
        requires={"eval_result.json", "candidate.py", "aide_target.json", "tree_state.json"},
        produces=UPDATE_WRITES,
    )


def build_aide_knobs() -> list[OptKnob]:
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_aide_memory() -> list[MemoryDeclaration]:
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_aide_workflow() -> Workflow:
    """Lower aide to the flat DAG the spine executes."""
    action_gate = gate(
        "action_gate",
        "python -m srf.ops.aide.gate action",
        reads={"aide_action.txt"},
        gate_prompt="draft a new solution, improve the best node, or debug a buggy node.",
    )
    action = Conditional(
        action_gate,
        {
            "draft": _draft_package(),
            "improve": _improve_package(),
            "debug": _debug_package(),
        },
        name="aide-action",
    )
    iteration = Sequential(
        _policy_package(),
        action,
        _eval_package(),
        _update_package(),
        name="aide-iteration",
    )
    study = loop(iteration, budget_gate(), name="aide")
    root = Sequential(task_input(), seed_run(SEEDS), study, name="aide")
    return compile_mode("aide", declared(root, knobs=KNOBS, memory=MEMORY))
