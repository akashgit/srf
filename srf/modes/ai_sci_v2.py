"""AI Scientist V2 mode — 4-stage BFTS pipeline.

DAG structure:
  Sequential(
    stage_1: Loop(AIDE-like tree search for initial implementation),
    stage_transition,
    stage_2: Loop(AIDE-like tree search for baseline tuning),
    stage_transition,
    stage_3: Loop(AIDE-like tree search for creative research),
    stage_transition,
    stage_4: Loop(AIDE-like tree search for ablation),
  )
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
    Sequential,
    Workflow,
)

STAGE_PROMPTS = {
    "initial": "You are AI Scientist V2 in the INITIAL IMPLEMENTATION stage. Produce a working solution.",
    "tuning": "You are AI Scientist V2 in the BASELINE TUNING stage. Optimize parameters and performance.",
    "creative": "You are AI Scientist V2 in the CREATIVE RESEARCH stage. Try novel approaches.",
    "ablation": "You are AI Scientist V2 in the ABLATION STUDIES stage. Verify which components matter.",
}


def build_ai_sci_v2_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.7,
                bounds=[0.3, 0.5, 0.7, 0.9], node_id="generate",
                description="LLM sampling temperature"),
        OptKnob(name="stage_budget", kind="threshold", default=10.0,
                bounds=[5.0, 10.0, 20.0, 50.0], node_id="stage",
                description="Budget per stage"),
        OptKnob(name="debug_prob", kind="threshold", default=0.3,
                bounds=[0.1, 0.2, 0.3, 0.5], node_id="policy",
                description="Debug probability"),
    ]


def build_ai_sci_v2_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="ai_sci_v2.tree", kind="kv", retention="run"),
        MemoryDeclaration(namespace="ai_sci_v2.stages", kind="log", retention="run"),
    ]


def _build_stage_loop(stage_name: str, stage_idx: int) -> Loop:
    policy = FnNode(
        name=f"policy_{stage_name}",
        callable_name="srf.ops.aide.ops:search_policy",
        reads={"tree_state.json"},
        writes={"aide_action.txt", "aide_target.json"},
    )

    draft_prompt = FnNode(
        name=f"draft_prompt_{stage_name}",
        callable_name="srf.ops.aide.ops:build_draft_prompt",
        reads={"task.yaml"},
        writes={"aide_prompt.md"},
    )
    draft_gen = LLMNode(
        name=f"draft_gen_{stage_name}",
        model="sonnet", temperature=0.7,
        system_prompt=STAGE_PROMPTS.get(stage_name, STAGE_PROMPTS["initial"]),
        reads={"aide_prompt.md"}, writes={"candidate.py"},
    )
    draft_pkg = Package(
        name=f"ai_sci_v2-draft-{stage_name}",
        nodes=[draft_prompt, draft_gen],
        edges=[Edge(source=f"draft_prompt_{stage_name}", target=f"draft_gen_{stage_name}")],
    )

    improve_prompt = FnNode(
        name=f"improve_prompt_{stage_name}",
        callable_name="srf.ops.aide.ops:build_improve_prompt",
        reads={"tree_state.json", "aide_target.json", "task.yaml"},
        writes={"aide_prompt.md"},
    )
    improve_gen = LLMNode(
        name=f"improve_gen_{stage_name}",
        model="sonnet", temperature=0.7,
        system_prompt=STAGE_PROMPTS.get(stage_name, STAGE_PROMPTS["tuning"]),
        reads={"aide_prompt.md"}, writes={"candidate.py"},
    )
    improve_pkg = Package(
        name=f"ai_sci_v2-improve-{stage_name}",
        nodes=[improve_prompt, improve_gen],
        edges=[Edge(source=f"improve_prompt_{stage_name}", target=f"improve_gen_{stage_name}")],
    )

    debug_prompt = FnNode(
        name=f"debug_prompt_{stage_name}",
        callable_name="srf.ops.aide.ops:build_debug_prompt",
        reads={"tree_state.json", "aide_target.json", "task.yaml"},
        writes={"aide_prompt.md"},
    )
    debug_gen = LLMNode(
        name=f"debug_gen_{stage_name}",
        model="sonnet", temperature=0.5,
        system_prompt="Fix bugs in the solution. Output a single fenced code block.",
        reads={"aide_prompt.md"}, writes={"candidate.py"},
    )
    debug_pkg = Package(
        name=f"ai_sci_v2-debug-{stage_name}",
        nodes=[debug_prompt, debug_gen],
        edges=[Edge(source=f"debug_prompt_{stage_name}", target=f"debug_gen_{stage_name}")],
    )

    action_gate = GateNode(
        name=f"action_gate_{stage_name}",
        evaluator_command="python -m srf.ops.aide.gate action",
    )

    action_cond = Conditional(
        name=f"ai_sci_v2-action-{stage_name}",
        gate=action_gate,
        branches={"DRAFT": draft_pkg, "IMPROVE": improve_pkg, "DEBUG": debug_pkg},
    )

    evaluate = FnNode(
        name=f"eval_{stage_name}",
        callable_name="srf.ops.common.sandbox:run_eval",
        reads={"candidate.py", "task.yaml"},
        writes={"eval_result.json"},
    )

    tree_update = FnNode(
        name=f"tree_update_{stage_name}",
        callable_name="srf.ops.aide.ops:update_tree",
        reads={"eval_result.json", "candidate.py", "aide_target.json", "tree_state.json"},
        writes={"tree_state.json", "aide_state.json", "best_solution.py"},
    )

    budget_gate = GateNode(
        name=f"budget_{stage_name}",
        evaluator_command="python -m srf.ops.common.budget check",
    )

    iteration = Sequential(
        name=f"ai_sci_v2-iter-{stage_name}",
        children=[policy, action_cond, evaluate, tree_update],
    )

    return Loop(
        name=f"ai_sci_v2-stage-{stage_name}",
        body=iteration,
        gate=budget_gate,
        max_iterations=100,
    )


def build_ai_sci_v2_workflow() -> Workflow:
    stage_names = ["initial", "tuning", "creative", "ablation"]
    children: list = []

    for i, stage_name in enumerate(stage_names):
        children.append(_build_stage_loop(stage_name, i))
        if i < len(stage_names) - 1:
            transition = FnNode(
                name=f"transition_{i}",
                callable_name="srf.ops.ai_sci.ops:stage_transition",
                reads={"ai_sci_state.json"},
                writes={"ai_sci_state.json"},
            )
            children.append(transition)

    root = Sequential(
        name="ai_sci_v2-pipeline",
        children=children,
    )

    return Workflow(
        name="ai_sci_v2",
        root=root,
        knobs=build_ai_sci_v2_knobs(),
        memory=build_ai_sci_v2_memory(),
    )
