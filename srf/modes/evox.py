"""EvoX Meta mode — meta-learned evolution.

The search strategy itself evolves based on population history.

DAG structure:
  Loop(body=Sequential(sample, prompt, generate, eval, update), gate=budget)
"""

from __future__ import annotations

from srf._factory_shim import (
    FnNode, GateNode, LLMNode, Loop, MemoryDeclaration, OptKnob, Sequential, Workflow,
)

SYSTEM_PROMPT = (
    "You are EvoX Meta, an evolutionary optimizer where the strategy itself evolves. "
    "Apply the current meta-strategy to produce an improved solution. "
    "Output a single fenced code block."
)


def build_evox_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.8,
                bounds=[0.5, 0.7, 0.8, 0.9, 1.0], node_id="generate",
                description="LLM sampling temperature"),
        OptKnob(name="parent_selection", kind="prompt", default="best",
                bounds=["best", "epsilon_greedy", "power_law", "uniform"],
                node_id="sample", description="Default parent selection strategy"),
        OptKnob(name="meta_interval", kind="threshold", default=15.0,
                bounds=[10.0, 15.0, 20.0], node_id="meta",
                description="Iterations between meta-evolution"),
    ]


def build_evox_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="evox.population", kind="kv", retention="run"),
        MemoryDeclaration(namespace="evox.meta_strategies", kind="log", retention="run"),
    ]


def build_evox_workflow() -> Workflow:
    sample = FnNode(name="sample", callable_name="srf.ops.evox.ops:sample_with_strategy",
                    reads={"population.json", "evox_state.json"}, writes={"selected_parent.json"})
    prompt = FnNode(name="build_prompt", callable_name="srf.ops.evox.ops:build_evox_prompt",
                    reads={"selected_parent.json", "evox_state.json", "task.yaml"}, writes={"evox_prompt.md"})
    generate = LLMNode(name="generate", model="sonnet", temperature=0.8,
                       system_prompt=SYSTEM_PROMPT, reads={"evox_prompt.md"}, writes={"candidate.py"})
    evaluate = FnNode(name="sandbox_eval", callable_name="srf.ops.common.sandbox:run_eval",
                      reads={"candidate.py", "task.yaml"}, writes={"eval_result.json"})
    update = FnNode(name="archive_update", callable_name="srf.ops.evox.ops:update_evox_archive",
                    reads={"eval_result.json", "candidate.py", "selected_parent.json", "population.json"},
                    writes={"population.json", "evox_state.json", "best_solution.py"})
    budget_gate = GateNode(name="budget_check", evaluator_command="python -m srf.ops.common.budget check")

    iteration = Sequential(name="evox-iteration", children=[sample, prompt, generate, evaluate, update])
    loop = Loop(name="evox", body=iteration, gate=budget_gate, max_iterations=500)

    return Workflow(name="evox", root=loop, knobs=build_evox_knobs(), memory=build_evox_memory())
