"""AutoScientists mode — multi-agent team.

Multiple independent scientist agents attack the problem in parallel,
then a merge agent combines the best insights.

DAG structure:
  Sequential(
    build_prompt,
    Parallel(*[scientist_generate_eval] * N),
    build_merge_prompt,
    merge_llm,
    eval,
    update
  )
"""

from __future__ import annotations

from srf._factory_shim import (
    Edge, FnNode, GateNode, LLMNode, Loop, MemoryDeclaration, OptKnob,
    Package, Parallel, Port, Sequential, StateContract, Workflow,
)

SCIENTIST_PROMPT = (
    "You are an independent scientist agent. Generate a creative and unique solution. "
    "Output a single fenced code block."
)

MERGE_PROMPT = (
    "You are a merge agent. Combine the best insights from multiple scientists' solutions. "
    "Output a single fenced code block."
)


def build_autoscientists_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="n_scientists", kind="threshold", default=3.0,
                bounds=[2.0, 3.0, 5.0], node_id="parallel",
                description="Number of parallel scientist agents"),
        OptKnob(name="temperature", kind="threshold", default=0.9,
                bounds=[0.7, 0.8, 0.9, 1.0], node_id="generate",
                description="LLM sampling temperature"),
    ]


def build_autoscientists_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="autoscientists.solutions", kind="log", retention="run"),
    ]


def _build_scientist_package(index: int) -> Package:
    prompt = FnNode(name=f"scientist_prompt_{index}",
                    callable_name="srf.ops.autoscientists.ops:build_scientist_prompt",
                    reads={"task.yaml"}, writes={"scientist_prompt.md"})
    generate = LLMNode(name=f"scientist_gen_{index}", model="sonnet", temperature=0.9,
                       system_prompt=SCIENTIST_PROMPT,
                       reads={"scientist_prompt.md"}, writes={f"scientist_{index}.py"})
    evaluate = FnNode(name=f"scientist_eval_{index}",
                      callable_name="srf.ops.common.sandbox:run_eval",
                      reads={f"scientist_{index}.py", "task.yaml"}, writes={f"scientist_result_{index}.json"})
    return Package(
        name=f"scientist-{index}", nodes=[prompt, generate, evaluate],
        edges=[Edge(source=f"scientist_prompt_{index}", target=f"scientist_gen_{index}"),
               Edge(source=f"scientist_gen_{index}", target=f"scientist_eval_{index}")],
    )


def build_autoscientists_workflow() -> Workflow:
    n = 3
    scientist_pkgs = [_build_scientist_package(i) for i in range(n)]
    parallel = Parallel(name="parallel-scientists", children=scientist_pkgs)

    merge_prompt = FnNode(name="merge_prompt", callable_name="srf.ops.autoscientists.ops:build_merge_prompt",
                          reads={f"scientist_{i}.py" for i in range(n)} | {f"scientist_result_{i}.json" for i in range(n)},
                          writes={"merge_prompt.md"})
    merge_gen = LLMNode(name="merge_generate", model="sonnet", temperature=0.7,
                        system_prompt=MERGE_PROMPT, reads={"merge_prompt.md"}, writes={"candidate.py"})
    evaluate = FnNode(name="sandbox_eval", callable_name="srf.ops.common.sandbox:run_eval",
                      reads={"candidate.py", "task.yaml"}, writes={"eval_result.json"})
    update = FnNode(name="update", callable_name="srf.ops.autoscientists.ops:update_autoscientists",
                    reads={"eval_result.json", "candidate.py"},
                    writes={"autoscientists_state.json", "best_solution.py"})

    root = Sequential(name="autoscientists-main",
                      children=[parallel, merge_prompt, merge_gen, evaluate, update])

    return Workflow(name="autoscientists", root=root,
                    knobs=build_autoscientists_knobs(), memory=build_autoscientists_memory())
