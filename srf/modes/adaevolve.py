"""AdaEvolve mode — adaptive evolution with 3-level hierarchy.

Three nested Conditionals:
  1. Meta-strategy: META (radical change) vs NORMAL (incremental)
  2. Normal path: standard evolution loop
  3. Both paths share eval + archive update

DAG structure:
  Loop(body=Sequential(
    meta_gate_fn,
    Conditional(meta_gate, {NORMAL: normal_pkg, META: meta_pkg}),
    eval, archive_update
  ), gate=budget)
"""

from __future__ import annotations

from srf._factory_shim import (
    Conditional, Edge, FnNode, GateNode, LLMNode, Loop, MemoryDeclaration,
    OptKnob, Package, Sequential, Workflow,
)

SYSTEM_PROMPT_NORMAL = (
    "You are AdaEvolve in NORMAL mode. Incrementally improve the solution. "
    "Output a single fenced code block."
)

SYSTEM_PROMPT_META = (
    "You are AdaEvolve in META-STRATEGY mode. The search is stagnating. "
    "Try a fundamentally different approach. Be creative and bold. "
    "Output a single fenced code block."
)


def build_adaevolve_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.7,
                bounds=[0.3, 0.5, 0.7, 0.9, 1.0], node_id="generate",
                description="LLM sampling temperature"),
        OptKnob(name="parent_selection", kind="prompt", default="best",
                bounds=["best", "epsilon_greedy", "power_law", "uniform"],
                node_id="sample", description="Parent selection strategy"),
        OptKnob(name="meta_temperature", kind="threshold", default=1.0,
                bounds=[0.8, 0.9, 1.0], node_id="meta_generate",
                description="Temperature for meta-strategy exploration"),
    ]


def build_adaevolve_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="adaevolve.population", kind="kv", retention="run"),
        MemoryDeclaration(namespace="adaevolve.meta", kind="log", retention="run"),
    ]


def build_adaevolve_workflow() -> Workflow:
    sample = FnNode(name="adaptive_sample", callable_name="srf.ops.adaevolve.ops:adaptive_sample",
                    reads={"population.json", "adaevolve_state.json"}, writes={"selected_parent.json", "ada_stagnation.json"})

    meta_gate_fn = FnNode(name="meta_gate_fn", callable_name="srf.ops.adaevolve.ops:meta_strategy_gate_fn",
                          reads={"adaevolve_state.json"}, writes={"meta_decision.txt"})

    normal_prompt = FnNode(name="normal_prompt", callable_name="srf.ops.adaevolve.ops:build_ada_prompt",
                           reads={"selected_parent.json", "ada_stagnation.json", "task.yaml"}, writes={"ada_prompt.md"})
    normal_gen = LLMNode(name="normal_generate", model="sonnet", temperature=0.7,
                         system_prompt=SYSTEM_PROMPT_NORMAL, reads={"ada_prompt.md"}, writes={"candidate.py"})
    normal_pkg = Package(name="adaevolve-normal", nodes=[normal_prompt, normal_gen],
                         edges=[Edge(source="normal_prompt", target="normal_generate")])

    meta_prompt = FnNode(name="meta_prompt", callable_name="srf.ops.adaevolve.ops:build_ada_prompt",
                         reads={"selected_parent.json", "ada_stagnation.json", "task.yaml"}, writes={"ada_prompt.md"})
    meta_gen = LLMNode(name="meta_generate", model="sonnet", temperature=1.0,
                       system_prompt=SYSTEM_PROMPT_META, reads={"ada_prompt.md"}, writes={"candidate.py"})
    meta_pkg = Package(name="adaevolve-meta", nodes=[meta_prompt, meta_gen],
                       edges=[Edge(source="meta_prompt", target="meta_generate")])

    meta_gate = GateNode(name="meta_gate", evaluator_command="python -m srf.ops.adaevolve.gate meta_gate")

    strategy_cond = Conditional(name="adaevolve-strategy", gate=meta_gate,
                                branches={"NORMAL": normal_pkg, "META": meta_pkg})

    evaluate = FnNode(name="sandbox_eval", callable_name="srf.ops.common.sandbox:run_eval",
                      reads={"candidate.py", "task.yaml"}, writes={"eval_result.json"})
    update = FnNode(name="archive_update", callable_name="srf.ops.adaevolve.ops:update_ada_archive",
                    reads={"eval_result.json", "candidate.py", "selected_parent.json", "population.json"},
                    writes={"population.json", "adaevolve_state.json", "best_solution.py"})

    budget_gate = GateNode(name="budget_check", evaluator_command="python -m srf.ops.common.budget check")

    iteration = Sequential(name="adaevolve-iteration",
                           children=[sample, meta_gate_fn, strategy_cond, evaluate, update])
    loop = Loop(name="adaevolve", body=iteration, gate=budget_gate, max_iterations=500)

    return Workflow(name="adaevolve", root=loop, knobs=build_adaevolve_knobs(), memory=build_adaevolve_memory())
