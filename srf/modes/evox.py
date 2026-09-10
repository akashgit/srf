"""EvoX Meta mode — meta-learned evolution.

The search strategy itself evolves based on population history.

Graph:
  task_input → seed_run → Loop:
    sample → build_prompt → generate → sandbox_eval → archive_update
                                                       │
                    budget_check ◀─────────────────────┘
                                 ──reloop──▶ sample
                                 ──proceed─▶ exit_evox

``evox_state.json`` carries the current meta-strategy, so every iteration samples
under whichever strategy the archive update last recorded.
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
    "You are EvoX Meta, an evolutionary optimizer where the strategy itself evolves. "
    "Apply the current meta-strategy to produce an improved solution. "
    "Output a single fenced code block."
)

ARCHIVE_WRITES = {"population.json", "evox_state.json", "best_solution.py"}

SEEDS = ("population.json", "evox_state.json", "best_solution.py")
"""The mutable artifacts the loop reads or maintains, seeded before the first pass."""

KNOBS = [
    knob(
        "temperature",
        "threshold",
        0.8,
        [0.5, 0.7, 0.8, 0.9, 1.0],
        "generate",
        "LLM sampling temperature",
    ),
    knob(
        "parent_selection",
        "prompt",
        "best",
        ["best", "epsilon_greedy", "power_law", "uniform"],
        "sample",
        "Default parent selection strategy",
    ),
    knob(
        "meta_interval",
        "threshold",
        15.0,
        [10.0, 15.0, 20.0],
        "sample",
        "Iterations between meta-evolution",
    ),
]

MEMORY = [
    memory("evox.population", "kv"),
    memory("evox.meta_strategies", "log"),
]


def _sample_package():
    """Draw a parent using the meta-strategy recorded in the run state."""
    return chain(
        "evox-sample",
        [
            op(
                "sample",
                "srf.ops.evox.ops:sample_with_strategy",
                reads={"population.json", "evox_state.json"},
                writes={"selected_parent.json"},
            )
        ],
        inputs=[port("population", "population.json", "application/json")],
        outputs=[port("parent", "selected_parent.json", "application/json")],
        requires={"population.json", "evox_state.json"},
        produces={"selected_parent.json"},
    )


def _propose_package():
    """Turn the parent plus the current strategy into a prompt, then generate."""
    build_prompt = op(
        "build_prompt",
        "srf.ops.evox.ops:build_evox_prompt",
        reads={"selected_parent.json", "evox_state.json", "task.yaml"},
        writes={"evox_prompt.md"},
    )
    generate = llm(
        "generate",
        SYSTEM_PROMPT,
        temperature=0.8,
        reads={"evox_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "evox-propose",
        [build_prompt, generate],
        inputs=[port("parent", "selected_parent.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"selected_parent.json", "evox_state.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _update_package():
    """Fold the scored candidate into the population, and re-derive the strategy."""
    return single(
        op(
            "archive_update",
            "srf.ops.evox.ops:update_evox_archive",
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


def build_evox_knobs():
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_evox_memory():
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_evox_workflow() -> Workflow:
    """Lower evox to the flat DAG the spine executes."""
    iteration = Sequential(
        _sample_package(),
        _propose_package(),
        eval_step("sandbox_eval"),
        _update_package(),
        name="evox-iteration",
    )
    study = loop(iteration, budget_gate(), name="evox")
    root = Sequential(task_input(), seed_run(SEEDS), study, name="evox")
    return compile_mode("evox", declared(root, knobs=KNOBS, memory=MEMORY))
