"""OpenEvolve mode — multi-island MAP-Elites evolution.

DAG structure:
  Loop(body=Sequential(sample, prompt, generate, eval, update_island), gate=budget)
"""

from __future__ import annotations

from srf._factory_shim import (
    Edge,
    FnNode,
    GateNode,
    LLMNode,
    Loop,
    MemoryDeclaration,
    OptKnob,
    Sequential,
    Workflow,
)

SYSTEM_PROMPT = (
    "You are OpenEvolve, an evolutionary code optimization agent. "
    "Given a parent solution and optional inspiration, produce a mutated improvement. "
    "Output a single fenced code block."
)


def build_openevolve_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.8,
                bounds=[0.5, 0.7, 0.8, 0.9, 1.0], node_id="generate",
                description="LLM sampling temperature"),
        OptKnob(name="n_islands", kind="threshold", default=3.0,
                bounds=[2.0, 3.0, 5.0], node_id="island",
                description="Number of islands"),
        OptKnob(name="migration_interval", kind="threshold", default=10.0,
                bounds=[5.0, 10.0, 20.0], node_id="migration",
                description="Generations between migrations"),
        OptKnob(name="parent_selection", kind="prompt", default="best",
                bounds=["best", "epsilon_greedy", "power_law", "uniform"],
                node_id="sample", description="Parent selection strategy"),
    ]


def build_openevolve_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="openevolve.islands", kind="kv", retention="run"),
        MemoryDeclaration(namespace="openevolve.migrations", kind="log", retention="run"),
    ]


def build_openevolve_workflow() -> Workflow:
    sample = FnNode(
        name="sample",
        callable_name="srf.ops.openevolve.ops:sample_parent_and_inspiration",
        reads={"island_populations.json"},
        writes={"selected_parent.json", "inspiration.json"},
    )
    prompt = FnNode(
        name="build_prompt",
        callable_name="srf.ops.openevolve.ops:build_evolve_prompt",
        reads={"selected_parent.json", "inspiration.json", "task.yaml"},
        writes={"evolve_prompt.md"},
    )
    generate = LLMNode(
        name="generate",
        model="sonnet", temperature=0.8,
        system_prompt=SYSTEM_PROMPT,
        reads={"evolve_prompt.md"}, writes={"candidate.py"},
    )
    evaluate = FnNode(
        name="sandbox_eval",
        callable_name="srf.ops.common.sandbox:run_eval",
        reads={"candidate.py", "task.yaml"},
        writes={"eval_result.json"},
    )
    update = FnNode(
        name="update_island",
        callable_name="srf.ops.openevolve.ops:update_island",
        reads={"eval_result.json", "candidate.py", "selected_parent.json", "island_populations.json"},
        writes={"island_populations.json", "openevolve_state.json", "best_solution.py"},
    )
    budget_gate = GateNode(name="budget_check", evaluator_command="python -m srf.ops.common.budget check")

    iteration = Sequential(name="openevolve-iteration", children=[sample, prompt, generate, evaluate, update])
    loop = Loop(name="openevolve", body=iteration, gate=budget_gate, max_iterations=500)

    return Workflow(name="openevolve", root=loop, knobs=build_openevolve_knobs(), memory=build_openevolve_memory())
