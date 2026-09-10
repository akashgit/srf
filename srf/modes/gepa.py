"""GEPA mode — reflective evolution with a merge branch.

Graph:
  task_input → seed_run → Loop:
    merge_decision ──mutate──▶ select_parent → build_reflective_prompt → generate_code
                   ──merge───▶ find_merge_candidates → build_merge_prompt → generate_merge
                              │
                              ▼
                   sandbox_eval → accept_or_reject
                              │
                              ▼
                        budget_check ──reloop──▶ merge_decision
                                      ──proceed─▶ exit

``merge_decision`` is a switch, not a rewind: both outcomes continue the same
iteration along different branches.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    Conditional,
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

SYSTEM_PROMPT_GENERATE = (
    "You are GEPA, a code evolution agent. Given a parent program, evaluation "
    "feedback, and a history of rejected attempts, produce an improved version. "
    "Output a single fenced code block."
)

SYSTEM_PROMPT_MERGE = (
    "You are GEPA merge agent. Given two or three programs with their scores, "
    "combine their strengths into a single improved program. "
    "Output a single fenced code block."
)

ACCEPT_WRITES = {
    "population.json",
    "genealogy.json",
    "rejection_history.json",
    "accepted_history.json",
    "gepa_state.json",
    "best_solution.py",
}

KNOBS = [
    knob(
        "temperature",
        "threshold",
        0.7,
        [0.3, 0.5, 0.7, 0.9, 1.0],
        "generate_code",
        "LLM sampling temperature",
    ),
    knob(
        "parent_selection",
        "prompt",
        "best",
        ["best", "pareto", "epsilon_greedy"],
        "select_parent",
        "How parents are chosen for mutation",
    ),
    knob(
        "max_rejection_context",
        "threshold",
        5.0,
        [3.0, 5.0, 8.0, 12.0],
        "build_reflective_prompt",
        "Rejected attempts shown in reflective prompt",
    ),
    knob(
        "merge_stagnation_threshold",
        "threshold",
        15.0,
        [5.0, 10.0, 15.0, 20.0, 30.0],
        "find_merge_candidates",
        "Iterations without improvement before merge triggers",
    ),
    knob(
        "acceptance_mode",
        "prompt",
        "strict",
        ["strict", "lenient", "off"],
        "accept_or_reject",
        "How strict the acceptance gate is",
    ),
]

SEEDS = (
    "population.json",
    "genealogy.json",
    "rejection_history.json",
    "accepted_history.json",
    "gepa_state.json",
    "best_solution.py",
)

MEMORY = [
    memory("gepa.population", "kv"),
    memory("gepa.genealogy", "graph"),
    memory("gepa.rejections", "log"),
]


def _mutate_package():
    """One mutation of a selected parent, conditioned on the rejection history."""
    select_parent = op(
        "select_parent",
        "srf.ops.gepa.population:select_parent",
        reads={"population.json", "gepa_state.json"},
        writes={"selected_parent.json"},
    )
    build_reflective = op(
        "build_reflective_prompt",
        "srf.ops.gepa.prompts:build_reflective_prompt",
        reads={
            "selected_parent.json",
            "rejection_history.json",
            "accepted_history.json",
            "task.yaml",
        },
        writes={"mutate_prompt.md"},
    )
    generate_code = llm(
        "generate_code",
        SYSTEM_PROMPT_GENERATE,
        temperature=0.7,
        reads={"mutate_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "gepa-mutate",
        [select_parent, build_reflective, generate_code],
        inputs=[port("population", "population.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"population.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _merge_package():
    """One merge of the best programs — the stagnation-escape branch."""
    find_merge = op(
        "find_merge_candidates",
        "srf.ops.gepa.merge:find_triplet_or_top2",
        reads={"population.json", "genealogy.json"},
        writes={"merge_candidates.json"},
    )
    build_merge = op(
        "build_merge_prompt",
        "srf.ops.gepa.prompts:build_merge_prompt",
        reads={"merge_candidates.json", "task.yaml"},
        writes={"merge_prompt.md"},
    )
    generate_merge = llm(
        "generate_merge",
        SYSTEM_PROMPT_MERGE,
        temperature=0.7,
        reads={"merge_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "gepa-merge",
        [find_merge, build_merge, generate_merge],
        inputs=[port("population", "population.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"population.json", "genealogy.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _eval_package():
    """Score the candidate, then accept or reject it into the population."""
    sandbox_eval = op(
        "sandbox_eval",
        "srf.ops.common.sandbox:run_eval",
        reads={"candidate.py", "task.yaml"},
        writes={"eval_result.json"},
    )
    accept = op(
        "accept_or_reject",
        "srf.ops.gepa.acceptance:accept_or_reject",
        reads={
            "eval_result.json",
            "candidate.py",
            "selected_parent.json",
            "population.json",
            "genealogy.json",
            "gepa_state.json",
        },
        writes=ACCEPT_WRITES,
    )
    return chain(
        "gepa-eval",
        [sandbox_eval, accept],
        inputs=[port("candidate", "candidate.py", "text/x-python")],
        outputs=[port("result", "eval_result.json", "application/json")],
        requires={"candidate.py", "task.yaml"},
        produces=ACCEPT_WRITES | {"eval_result.json"},
    )


def build_gepa_knobs():
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_gepa_memory():
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_gepa_workflow() -> Workflow:
    """Lower gepa to the flat DAG the spine executes."""
    decision = gate(
        "merge_decision",
        "python -m srf.ops.gepa.decision should_merge",
        reads={"gepa_state.json", "population.json"},
        gate_prompt="mutate the selected parent, or merge the best programs.",
    )
    action = Conditional(
        decision,
        {"mutate": _mutate_package(), "merge": _merge_package()},
        name="gepa-action",
    )
    iteration = Sequential(action, _eval_package(), name="gepa-iteration")
    study = loop(iteration, budget_gate(), name="gepa")
    root = Sequential(task_input(), seed_run(SEEDS), study, name="gepa")
    return compile_mode("gepa", declared(root, knobs=KNOBS, memory=MEMORY))
