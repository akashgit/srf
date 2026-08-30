"""ShinkaEvolve mode — reflection + evolution.

DAG structure:
  Loop(body=Sequential(sample_reflect, prompt, generate, eval, archive_update), gate=budget)
"""

from __future__ import annotations

from srf._factory_shim import (
    FnNode, GateNode, LLMNode, Loop, MemoryDeclaration, OptKnob, Sequential, Workflow,
)

SYSTEM_PROMPT = (
    "You are ShinkaEvolve, an evolutionary optimizer with reflection capabilities. "
    "Evolve the solution using insights from past attempts. "
    "Output a single fenced code block."
)


def build_shinka_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.7,
                bounds=[0.3, 0.5, 0.7, 0.9], node_id="generate",
                description="LLM sampling temperature"),
        OptKnob(name="reflect_interval", kind="threshold", default=5.0,
                bounds=[3.0, 5.0, 10.0], node_id="reflect",
                description="Iterations between reflections"),
        OptKnob(name="parent_selection", kind="prompt", default="best",
                bounds=["best", "epsilon_greedy", "ucb", "uniform"],
                node_id="sample", description="Parent selection strategy"),
    ]


def build_shinka_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="shinka.population", kind="kv", retention="run"),
        MemoryDeclaration(namespace="shinka.reflections", kind="log", retention="run"),
    ]


def build_shinka_workflow() -> Workflow:
    sample = FnNode(name="sample_reflect", callable_name="srf.ops.shinka.ops:sample_and_reflect",
                    reads={"population.json", "shinka_state.json"}, writes={"selected_parent.json", "reflection.md"})
    prompt = FnNode(name="build_prompt", callable_name="srf.ops.shinka.ops:build_shinka_prompt",
                    reads={"selected_parent.json", "reflection.md", "task.yaml"}, writes={"shinka_prompt.md"})
    generate = LLMNode(name="generate", model="sonnet", temperature=0.7, system_prompt=SYSTEM_PROMPT,
                       reads={"shinka_prompt.md"}, writes={"candidate.py"})
    evaluate = FnNode(name="sandbox_eval", callable_name="srf.ops.common.sandbox:run_eval",
                      reads={"candidate.py", "task.yaml"}, writes={"eval_result.json"})
    update = FnNode(name="archive_update", callable_name="srf.ops.shinka.ops:update_shinka_archive",
                    reads={"eval_result.json", "candidate.py", "selected_parent.json", "population.json"},
                    writes={"population.json", "shinka_state.json", "best_solution.py"})
    budget_gate = GateNode(name="budget_check", evaluator_command="python -m srf.ops.common.budget check")

    iteration = Sequential(name="shinka-iteration", children=[sample, prompt, generate, evaluate, update])
    loop = Loop(name="shinka", body=iteration, gate=budget_gate, max_iterations=500)

    return Workflow(name="shinka", root=loop, knobs=build_shinka_knobs(), memory=build_shinka_memory())
