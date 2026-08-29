"""GEPA mode — faithful Package implementation.

DAG structure:
  Loop(body=Sequential(Conditional(merge_gate, {PROCEED: mutate_pkg, RELOOP: merge_pkg}), eval_pkg),
       gate=budget_gate, max_iterations=500)
"""

from __future__ import annotations

from srf._factory_shim import (
    Conditional,
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

SYSTEM_PROMPT_GENERATE = (
    "You are GEPA, a code evolution agent. Given a parent program, evaluation "
    "feedback, and a history of rejected attempts, produce an improved version. "
    "Output a single fenced code block."
)

SYSTEM_PROMPT_MERGE = (
    "You are GEPA merge agent. Given two or three programs with their scores, "
    "combine their strengths into a single improved program. "
    "Output a single fenced code block."
)


def build_gepa_knobs() -> list[OptKnob]:
    return [
        OptKnob(
            name="temperature",
            kind="threshold",
            default=0.7,
            bounds=[0.3, 0.5, 0.7, 0.9, 1.0],
            node_id="generate_code",
            description="LLM sampling temperature",
        ),
        OptKnob(
            name="parent_selection",
            kind="prompt",
            default="best",
            bounds=["best", "pareto", "epsilon_greedy"],
            node_id="select_parent",
            description="How parents are chosen for mutation",
        ),
        OptKnob(
            name="max_rejection_context",
            kind="threshold",
            default=5.0,
            bounds=[3.0, 5.0, 8.0, 12.0],
            node_id="build_reflective_prompt",
            description="Rejected attempts shown in reflective prompt",
        ),
        OptKnob(
            name="merge_stagnation_threshold",
            kind="threshold",
            default=15.0,
            bounds=[5.0, 10.0, 15.0, 20.0, 30.0],
            node_id="find_merge_candidates",
            description="Iterations without improvement before merge triggers",
        ),
        OptKnob(
            name="acceptance_mode",
            kind="prompt",
            default="strict",
            bounds=["strict", "lenient", "off"],
            node_id="accept_or_reject",
            description="How strict the acceptance gate is",
        ),
    ]


def build_gepa_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="gepa.population", kind="kv", retention="run"),
        MemoryDeclaration(namespace="gepa.genealogy", kind="graph", retention="run"),
        MemoryDeclaration(namespace="gepa.rejections", kind="log", retention="run"),
    ]


def build_mutate_package() -> Package:
    select_parent = FnNode(
        name="select_parent",
        callable_name="srf.ops.gepa.population:select_parent",
        reads={"population.json", "gepa_state.json"},
        writes={"selected_parent.json"},
    )
    build_reflective = FnNode(
        name="build_reflective_prompt",
        callable_name="srf.ops.gepa.prompts:build_reflective_prompt",
        reads={"selected_parent.json", "rejection_history.json", "accepted_history.json", "task.yaml"},
        writes={"mutate_prompt.md"},
    )
    generate_code = LLMNode(
        name="generate_code",
        model="sonnet",
        temperature=0.7,
        system_prompt=SYSTEM_PROMPT_GENERATE,
        reads={"mutate_prompt.md"},
        writes={"candidate.py"},
    )
    return Package(
        name="gepa-mutate",
        nodes=[select_parent, build_reflective, generate_code],
        edges=[
            Edge(source="select_parent", target="build_reflective_prompt"),
            Edge(source="build_reflective_prompt", target="generate_code"),
        ],
        inputs=[Port("population", "population.json")],
        outputs=[Port("candidate", "candidate.py")],
        state_contract=StateContract(
            requires={"population.json", "task.yaml"},
            produces={"candidate.py"},
        ),
    )


def build_merge_package() -> Package:
    find_merge = FnNode(
        name="find_merge_candidates",
        callable_name="srf.ops.gepa.merge:find_triplet_or_top2",
        reads={"population.json", "genealogy.json"},
        writes={"merge_candidates.json"},
    )
    build_merge = FnNode(
        name="build_merge_prompt",
        callable_name="srf.ops.gepa.prompts:build_merge_prompt",
        reads={"merge_candidates.json", "task.yaml"},
        writes={"merge_prompt.md"},
    )
    generate_merge = LLMNode(
        name="generate_merge",
        model="sonnet",
        temperature=0.7,
        system_prompt=SYSTEM_PROMPT_MERGE,
        reads={"merge_prompt.md"},
        writes={"candidate.py"},
    )
    return Package(
        name="gepa-merge",
        nodes=[find_merge, build_merge, generate_merge],
        edges=[
            Edge(source="find_merge_candidates", target="build_merge_prompt"),
            Edge(source="build_merge_prompt", target="generate_merge"),
        ],
        inputs=[Port("population", "population.json")],
        outputs=[Port("candidate", "candidate.py")],
        state_contract=StateContract(
            requires={"population.json", "genealogy.json", "task.yaml"},
            produces={"candidate.py"},
        ),
    )


def build_eval_package() -> Package:
    sandbox_eval = FnNode(
        name="sandbox_eval",
        callable_name="srf.ops.common.sandbox:run_eval",
        reads={"candidate.py", "task.yaml"},
        writes={"eval_result.json"},
    )
    accept = FnNode(
        name="accept_or_reject",
        callable_name="srf.ops.gepa.acceptance:accept_or_reject",
        reads={"eval_result.json", "candidate.py", "selected_parent.json",
               "population.json", "genealogy.json", "gepa_state.json"},
        writes={"population.json", "genealogy.json", "rejection_history.json",
                "accepted_history.json", "gepa_state.json", "best_solution.py"},
    )
    return Package(
        name="gepa-eval",
        nodes=[sandbox_eval, accept],
        edges=[Edge(source="sandbox_eval", target="accept_or_reject")],
        inputs=[Port("candidate", "candidate.py")],
        outputs=[Port("result", "eval_result.json")],
        state_contract=StateContract(
            requires={"candidate.py", "task.yaml"},
            produces={"eval_result.json", "best_solution.py"},
        ),
    )


def build_gepa_workflow() -> Workflow:
    """Build the complete GEPA workflow as specified in the design doc."""
    mutate_pkg = build_mutate_package()
    merge_pkg = build_merge_package()
    eval_pkg = build_eval_package()

    merge_gate = GateNode(
        name="merge_decision",
        evaluator_command="python -m srf.ops.gepa.decision should_merge",
    )

    budget_gate = GateNode(
        name="budget_check",
        evaluator_command="python -m srf.ops.common.budget check",
    )

    action_pkg = Conditional(
        name="gepa-action",
        gate=merge_gate,
        branches={"PROCEED": mutate_pkg, "RELOOP": merge_pkg},
    )

    iteration = Sequential(
        name="gepa-iteration",
        children=[action_pkg, eval_pkg],
    )

    gepa_loop = Loop(
        name="gepa",
        body=iteration,
        gate=budget_gate,
        max_iterations=500,
    )

    return Workflow(
        name="gepa",
        root=gepa_loop,
        knobs=build_gepa_knobs(),
        memory=build_gepa_memory(),
    )
