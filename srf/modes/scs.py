"""SCS mode — Stochastic Code Search (archive-based prompting).

DAG structure:
  Loop(body=Sequential(sample, prompt, generate, eval, archive_update), gate=budget)
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
    Package,
    Port,
    Sequential,
    StateContract,
    Workflow,
)

SYSTEM_PROMPT = (
    "You are SCS, a stochastic code search agent. Given archive context showing "
    "the best solutions found so far, produce an improved version. "
    "Output a single fenced code block."
)


def build_scs_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.7,
                bounds=[0.3, 0.5, 0.7, 0.9, 1.0], node_id="generate_code",
                description="LLM sampling temperature"),
        OptKnob(name="parent_selection", kind="prompt", default="best",
                bounds=["best", "epsilon_greedy", "power_law", "uniform"],
                node_id="sample", description="Parent selection strategy"),
    ]


def build_scs_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="scs.population", kind="kv", retention="run"),
        MemoryDeclaration(namespace="scs.archive", kind="log", retention="run"),
    ]


def build_scs_workflow() -> Workflow:
    sample = FnNode(
        name="sample",
        callable_name="srf.ops.scs.ops:sample_from_archive",
        reads={"population.json"},
        writes={"selected_parent.json"},
    )
    prompt = FnNode(
        name="build_prompt",
        callable_name="srf.ops.scs.ops:build_scs_prompt",
        reads={"selected_parent.json", "population.json", "task.yaml"},
        writes={"scs_prompt.md"},
    )
    generate = LLMNode(
        name="generate_code",
        model="sonnet",
        temperature=0.7,
        system_prompt=SYSTEM_PROMPT,
        reads={"scs_prompt.md"},
        writes={"candidate.py"},
    )
    evaluate = FnNode(
        name="sandbox_eval",
        callable_name="srf.ops.common.sandbox:run_eval",
        reads={"candidate.py", "task.yaml"},
        writes={"eval_result.json"},
    )
    archive_update = FnNode(
        name="archive_update",
        callable_name="srf.ops.scs.ops:update_archive",
        reads={"eval_result.json", "candidate.py", "selected_parent.json", "population.json"},
        writes={"population.json", "scs_state.json", "best_solution.py"},
    )
    budget_gate = GateNode(
        name="budget_check",
        evaluator_command="python -m srf.ops.common.budget check",
    )

    iteration = Sequential(
        name="scs-iteration",
        children=[sample, prompt, generate, evaluate, archive_update],
    )

    scs_loop = Loop(
        name="scs",
        body=iteration,
        gate=budget_gate,
        max_iterations=500,
    )

    return Workflow(
        name="scs",
        root=scs_loop,
        knobs=build_scs_knobs(),
        memory=build_scs_memory(),
    )
