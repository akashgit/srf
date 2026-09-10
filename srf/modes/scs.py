"""SCS mode — Stochastic Code Search (archive-based prompting).

Graph:
  task_input → seed_run → Loop:
    sample → build_prompt → generate_code → sandbox_eval → archive_update
                                                             │
                          budget_check ◀──────────────────────┘
                                       ──reloop──▶ sample
                                       ──proceed─▶ exit_scs

The archive is ``population.json``: each iteration samples a parent from it,
proposes a candidate, scores it, and folds the result back in. The loop is a
flat DAG — ``budget_check``'s ``reloop`` edge is the only cycle the spine sees.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    Sequential,
    budget_gate,
    chain,
    compile_mode,
    declared,
    eval_step,
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

SYSTEM_PROMPT = (
    "You are SCS, a stochastic code search agent. Given archive context showing "
    "the best solutions found so far, produce an improved version. "
    "Output a single fenced code block."
)

ARCHIVE_WRITES = {"population.json", "scs_state.json", "best_solution.py"}

SEEDS = ("population.json", "scs_state.json", "best_solution.py")
"""The mutable artifacts the loop reads or maintains, seeded before the first pass."""

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
        ["best", "epsilon_greedy", "power_law", "uniform"],
        "sample",
        "Parent selection strategy",
    ),
]

MEMORY = [
    memory("scs.population", "kv"),
    memory("scs.archive", "log"),
]


def _sample_package():
    """Draw one parent out of the archive, by the configured strategy."""
    return chain(
        "scs-sample",
        [
            op(
                "sample",
                "srf.ops.scs.ops:sample_from_archive",
                reads={"population.json"},
                writes={"selected_parent.json"},
            )
        ],
        inputs=[port("population", "population.json", "application/json")],
        outputs=[port("parent", "selected_parent.json", "application/json")],
        requires={"population.json"},
        produces={"selected_parent.json"},
    )


def _propose_package():
    """Turn the archive context into a prompt, then sample one candidate."""
    build_prompt = op(
        "build_prompt",
        "srf.ops.scs.ops:build_scs_prompt",
        reads={"selected_parent.json", "population.json", "task.yaml"},
        writes={"scs_prompt.md"},
    )
    generate_code = llm(
        "generate_code",
        SYSTEM_PROMPT,
        temperature=0.7,
        reads={"scs_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "scs-propose",
        [build_prompt, generate_code],
        inputs=[port("parent", "selected_parent.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"selected_parent.json", "population.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _update_package():
    """Fold the scored candidate back into the archive, and the best solution."""
    return single(
        op(
            "archive_update",
            "srf.ops.scs.ops:update_archive",
            reads={
                "eval_result.json",
                "candidate.py",
                "selected_parent.json",
                "population.json",
            },
            writes=ARCHIVE_WRITES,
        ),
        inputs=[port("result", "eval_result.json", "application/json")],
        outputs=[port("solution", "best_solution.py", "text/x-python")],
        requires={"eval_result.json", "candidate.py", "selected_parent.json"},
        produces=ARCHIVE_WRITES,
    )


def build_scs_knobs():
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_scs_memory():
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_scs_workflow() -> Workflow:
    """Lower scs to the flat DAG the spine executes."""
    iteration = Sequential(
        _sample_package(),
        _propose_package(),
        eval_step("sandbox_eval"),
        _update_package(),
        name="scs-iteration",
    )
    study = loop(iteration, budget_gate(), name="scs")
    root = Sequential(task_input(), seed_run(SEEDS), study, name="scs")
    return compile_mode("scs", declared(root, knobs=KNOBS, memory=MEMORY))
