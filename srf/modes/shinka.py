"""ShinkaEvolve mode — reflection + evolution.

Graph:
  task_input → seed_run → Loop:
    sample_reflect → build_prompt → generate → sandbox_eval → archive_update
                                                              │
                          budget_check ◀───────────────────────┘
                                       ──reloop──▶ sample_reflect
                                       ──proceed─▶ exit_shinka

Sampling and reflection are one op, so every iteration carries whatever insight
the history has produced; the archive update decides what survives.
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
    "You are ShinkaEvolve, an evolutionary optimizer with reflection capabilities. "
    "Evolve the solution using insights from past attempts. "
    "Output a single fenced code block."
)

ARCHIVE_WRITES = {"population.json", "shinka_state.json", "best_solution.py"}

SEEDS = ("population.json", "shinka_state.json", "best_solution.py")
"""The mutable artifacts the loop reads or maintains, seeded before the first pass."""

KNOBS = [
    knob(
        "temperature",
        "threshold",
        0.7,
        [0.3, 0.5, 0.7, 0.9],
        "generate",
        "LLM sampling temperature",
    ),
    knob(
        "reflect_interval",
        "threshold",
        5.0,
        [3.0, 5.0, 10.0],
        "sample_reflect",
        "Iterations between reflections",
    ),
    knob(
        "parent_selection",
        "prompt",
        "best",
        ["best", "epsilon_greedy", "ucb", "uniform"],
        "sample_reflect",
        "Parent selection strategy",
    ),
]

MEMORY = [
    memory("shinka.population", "kv"),
    memory("shinka.reflections", "log"),
]


def _sample_package():
    """Sample a parent and, every ``reflect_interval`` evals, write a reflection."""
    return chain(
        "shinka-sample",
        [
            op(
                "sample_reflect",
                "srf.ops.shinka.ops:sample_and_reflect",
                reads={"population.json", "shinka_state.json"},
                writes={"selected_parent.json", "reflection.md"},
            )
        ],
        inputs=[port("population", "population.json", "application/json")],
        outputs=[port("parent", "selected_parent.json", "application/json")],
        requires={"population.json", "shinka_state.json"},
        produces={"selected_parent.json", "reflection.md"},
    )


def _propose_package():
    """Turn parent plus reflection into a prompt, then sample one candidate."""
    build_prompt = op(
        "build_prompt",
        "srf.ops.shinka.ops:build_shinka_prompt",
        reads={"selected_parent.json", "reflection.md", "task.yaml"},
        writes={"shinka_prompt.md"},
    )
    generate = llm(
        "generate",
        SYSTEM_PROMPT,
        temperature=0.7,
        reads={"shinka_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "shinka-propose",
        [build_prompt, generate],
        inputs=[port("parent", "selected_parent.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"selected_parent.json", "reflection.md", "task.yaml"},
        produces={"candidate.py"},
    )


def _update_package():
    """Fold the scored candidate into the population and the eval history."""
    return single(
        op(
            "archive_update",
            "srf.ops.shinka.ops:update_shinka_archive",
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


def build_shinka_knobs():
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_shinka_memory():
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_shinka_workflow() -> Workflow:
    """Lower shinka to the flat DAG the spine executes."""
    iteration = Sequential(
        _sample_package(),
        _propose_package(),
        eval_step("sandbox_eval"),
        _update_package(),
        name="shinka-iteration",
    )
    study = loop(iteration, budget_gate(), name="shinka")
    root = Sequential(task_input(), seed_run(SEEDS), study, name="shinka")
    return compile_mode("shinka", declared(root, knobs=KNOBS, memory=MEMORY))
