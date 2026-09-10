"""OpenEvolve mode — multi-island MAP-Elites evolution.

Graph:
  task_input → seed_run → Loop:
    sample → build_prompt → generate → sandbox_eval → update_island
                                                          │
                                                          ▼
                                    budget_check ──reloop──▶ sample
                                                 ──proceed─▶ exit

An iteration samples a parent and its inspiration from the island archive,
mutates it, scores the candidate, then writes the result back into
``island_populations.json`` — the archive the next iteration samples from.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    MemoryDeclaration,
    OptKnob,
    Sequential,
    budget_gate,
    compile_mode,
    declared,
    eval_step,
    knob,
    llm,
    loop,
    memory,
    op,
    seed_run,
    single,
    task_input,
)

SYSTEM_PROMPT = (
    "You are OpenEvolve, an evolutionary code optimization agent. "
    "Given a parent solution and optional inspiration, produce a mutated improvement. "
    "Output a single fenced code block."
)

KNOBS: list[OptKnob] = [
    knob(
        "temperature",
        "threshold",
        0.8,
        [0.5, 0.7, 0.8, 0.9, 1.0],
        "generate",
        "LLM sampling temperature",
    ),
    knob("n_islands", "threshold", 3.0, [2.0, 3.0, 5.0], "update_island", "Number of islands"),
    knob(
        "migration_interval",
        "threshold",
        10.0,
        [5.0, 10.0, 20.0],
        "update_island",
        "Generations between migrations",
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

SEEDS = ("island_populations.json",)
"""Sampled on the loop's first pass, written back by ``update_island`` afterwards."""

MEMORY: list[MemoryDeclaration] = [
    memory("openevolve.islands", "kv"),
    memory("openevolve.migrations", "log"),
]

UPDATE_WRITES = {"island_populations.json", "openevolve_state.json", "best_solution.py"}


def _iteration_package():
    """One generation: sample a parent, mutate it, score it, update its island."""
    sample = single(
        op(
            "sample",
            "srf.ops.openevolve.ops:sample_parent_and_inspiration",
            reads={"island_populations.json"},
            writes={"selected_parent.json", "inspiration.json"},
        ),
        requires={"island_populations.json"},
        produces={"selected_parent.json", "inspiration.json"},
    )
    prompt = single(
        op(
            "build_prompt",
            "srf.ops.openevolve.ops:build_evolve_prompt",
            reads={"selected_parent.json", "inspiration.json", "task.yaml"},
            writes={"evolve_prompt.md"},
        ),
        requires={"selected_parent.json", "inspiration.json", "task.yaml"},
        produces={"evolve_prompt.md"},
    )
    generate = single(
        llm(
            "generate",
            SYSTEM_PROMPT,
            temperature=0.8,
            reads={"evolve_prompt.md"},
            writes={"candidate.py"},
        ),
        requires={"evolve_prompt.md"},
        produces={"candidate.py"},
    )
    update = single(
        op(
            "update_island",
            "srf.ops.openevolve.ops:update_island",
            reads={
                "eval_result.json",
                "candidate.py",
                "selected_parent.json",
                "island_populations.json",
            },
            writes=UPDATE_WRITES,
        ),
        requires={"eval_result.json", "candidate.py", "selected_parent.json"},
        produces=UPDATE_WRITES,
    )
    return Sequential(
        sample,
        prompt,
        generate,
        eval_step("sandbox_eval"),
        update,
        name="openevolve-iteration",
    )


def build_openevolve_knobs() -> list[OptKnob]:
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_openevolve_memory() -> list[MemoryDeclaration]:
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_openevolve_workflow() -> Workflow:
    """Lower openevolve to the flat DAG the spine executes."""
    study = loop(_iteration_package(), budget_gate(), name="openevolve")
    root = Sequential(task_input(), seed_run(SEEDS), study, name="openevolve")
    return compile_mode("openevolve", declared(root, knobs=KNOBS, memory=MEMORY))
