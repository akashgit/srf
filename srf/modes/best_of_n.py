"""Best-of-N mode — IID sampling.

DAG structure:
  Sequential(Parallel(*[generate_eval_pkg] * N), FnNode(select_best))
"""

from __future__ import annotations

from srf._factory_shim import (
    Edge,
    FnNode,
    LLMNode,
    MemoryDeclaration,
    OptKnob,
    Package,
    Parallel,
    Port,
    Sequential,
    StateContract,
    Workflow,
)

SYSTEM_PROMPT = (
    "You are a code optimization agent. Given a task description and initial code, "
    "produce an improved solution. Output a single fenced code block."
)


def build_best_of_n_knobs() -> list[OptKnob]:
    return [
        OptKnob(
            name="n_candidates",
            kind="threshold",
            default=5.0,
            bounds=[3.0, 5.0, 10.0, 20.0],
            node_id="parallel_generate",
            description="Number of independent candidates to generate",
        ),
        OptKnob(
            name="temperature",
            kind="threshold",
            default=0.8,
            bounds=[0.5, 0.7, 0.8, 0.9, 1.0],
            node_id="generate_code",
            description="LLM sampling temperature",
        ),
    ]


def build_best_of_n_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="best_of_n.candidates", kind="log", retention="run"),
    ]


def _build_generate_eval_package(index: int) -> Package:
    prompt_builder = FnNode(
        name=f"build_prompt_{index}",
        callable_name="srf.ops.best_of_n.ops:build_candidate_prompt",
        reads={"task.yaml"},
        writes={f"candidate_prompt.md"},
    )
    generate = LLMNode(
        name=f"generate_{index}",
        model="sonnet",
        temperature=0.8,
        system_prompt=SYSTEM_PROMPT,
        reads={"candidate_prompt.md"},
        writes={f"candidate_{index}.py"},
    )
    eval_node = FnNode(
        name=f"eval_{index}",
        callable_name="srf.ops.common.sandbox:run_eval",
        reads={f"candidate_{index}.py", "task.yaml"},
        writes={f"eval_result_{index}.json"},
    )
    return Package(
        name=f"best_of_n-gen-eval-{index}",
        nodes=[prompt_builder, generate, eval_node],
        edges=[
            Edge(source=f"build_prompt_{index}", target=f"generate_{index}"),
            Edge(source=f"generate_{index}", target=f"eval_{index}"),
        ],
        inputs=[Port("task", "task.yaml")],
        outputs=[Port("result", f"eval_result_{index}.json")],
        state_contract=StateContract(
            requires={"task.yaml"},
            produces={f"candidate_{index}.py", f"eval_result_{index}.json"},
        ),
    )


def build_best_of_n_workflow() -> Workflow:
    n = 5
    gen_eval_packages = [_build_generate_eval_package(i) for i in range(n)]

    parallel_gen = Parallel(
        name="parallel-generate",
        children=gen_eval_packages,
    )

    select_best = FnNode(
        name="select_best",
        callable_name="srf.ops.best_of_n.ops:select_best_candidate",
        reads={f"eval_result_{i}.json" for i in range(n)} | {f"candidate_{i}.py" for i in range(n)},
        writes={"best_solution.py", "best_of_n_result.json"},
    )

    root = Sequential(
        name="best_of_n-main",
        children=[parallel_gen, select_best],
    )

    return Workflow(
        name="best_of_n",
        root=root,
        knobs=build_best_of_n_knobs(),
        memory=build_best_of_n_memory(),
    )
