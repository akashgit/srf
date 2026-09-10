"""AI Scientist V2 mode — four-stage BFTS pipeline.

Graph:
  task_input → seed_run → stage(initial) → transition_0 → stage(tuning)
                        → transition_1 → stage(creative) → transition_2
                        → stage(ablation)

Each stage is its own study loop over the shared tree:

  policy_<stage> → action_gate_<stage> ──draft───▶ draft_prompt/draft_gen
                                       ──improve─▶ improve_prompt/improve_gen
                                       ──debug───▶ debug_prompt/debug_gen
                                                   │
                                                   ▼
                     join_ai_sci_v2-action-<stage> → eval_<stage>
                                                   → tree_update_<stage>
                                                   → budget_<stage>
                                       ──reloop──▶ policy_<stage>
                                       ──proceed─▶ exit_ai_sci_v2-stage-<stage>

``transition_<i>`` sits between two stages, so the pipeline advances only once a
stage's loop has spent its budget. Every node id carries its stage suffix: the
four loops contribute distinct ids to one flat DAG.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    Conditional,
    MemoryDeclaration,
    OptKnob,
    Package,
    Sequential,
    budget_gate,
    chain,
    compile_mode,
    declared,
    gate,
    knob,
    llm,
    loop,
    memory,
    op,
    port,
    seed_run,
    single,
    task_input,
)

STAGE_PROMPTS = {
    "initial": "You are AI Scientist V2 in the INITIAL IMPLEMENTATION stage. Produce a working solution.",
    "tuning": "You are AI Scientist V2 in the BASELINE TUNING stage. Optimize parameters and performance.",
    "creative": "You are AI Scientist V2 in the CREATIVE RESEARCH stage. Try novel approaches.",
    "ablation": "You are AI Scientist V2 in the ABLATION STUDIES stage. Verify which components matter.",
}

DEBUG_PROMPT = "Fix bugs in the solution. Output a single fenced code block."

STAGE_NAMES = ("initial", "tuning", "creative", "ablation")

KNOBS = [
    knob(
        "temperature",
        "threshold",
        0.7,
        [0.3, 0.5, 0.7, 0.9],
        "draft_gen_initial",
        "LLM sampling temperature",
    ),
    knob(
        "stage_budget",
        "threshold",
        10.0,
        [5.0, 10.0, 20.0, 50.0],
        "budget_initial",
        "Budget per stage",
    ),
    knob(
        "debug_prob",
        "threshold",
        0.3,
        [0.1, 0.2, 0.3, 0.5],
        "policy_initial",
        "Debug probability",
    ),
]

SEEDS = ("ai_sci_state.json", "aide_state.json", "tree_state.json")
"""Everything the first stage reads before it has written anything itself."""

MEMORY = [
    memory("ai_sci_v2.tree", "kv", "run"),
    memory("ai_sci_v2.stages", "log", "run"),
]

UPDATE_WRITES = {"tree_state.json", "aide_state.json", "best_solution.py"}


def _policy_package(stage_name: str) -> Package:
    """The stage's action switch: DRAFT, IMPROVE, or DEBUG."""
    return single(
        op(
            f"policy_{stage_name}",
            "srf.ops.aide.ops:search_policy",
            reads={"tree_state.json"},
            writes={"aide_action.txt", "aide_target.json"},
            notes="Score the tree and pick the stage's next action.",
        ),
        inputs=[port("tree", "tree_state.json", "application/json")],
        outputs=[port("action", "aide_action.txt", "text/plain")],
        requires={"tree_state.json"},
        produces={"aide_action.txt", "aide_target.json"},
    )


def _draft_package(stage_name: str) -> Package:
    """Draft a new solution under the stage's own system prompt."""
    build_prompt = op(
        f"draft_prompt_{stage_name}",
        "srf.ops.aide.ops:build_draft_prompt",
        reads={"task.yaml"},
        writes={"aide_prompt.md"},
        notes="Prompt with the task header and its initial code.",
    )
    generate = llm(
        f"draft_gen_{stage_name}",
        STAGE_PROMPTS.get(stage_name, STAGE_PROMPTS["initial"]),
        model="sonnet",
        temperature=0.7,
        reads={"aide_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        f"ai_sci_v2-draft-{stage_name}",
        [build_prompt, generate],
        inputs=[port("task", "task.yaml", "application/yaml")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"task.yaml"},
        produces={"candidate.py"},
    )


def _improve_package(stage_name: str) -> Package:
    """Improve the tree's best node under the stage's own system prompt."""
    build_prompt = op(
        f"improve_prompt_{stage_name}",
        "srf.ops.aide.ops:build_improve_prompt",
        reads={"tree_state.json", "aide_target.json", "task.yaml"},
        writes={"aide_prompt.md"},
        notes="Prompt with the target node's code and its search path.",
    )
    generate = llm(
        f"improve_gen_{stage_name}",
        STAGE_PROMPTS.get(stage_name, STAGE_PROMPTS["tuning"]),
        model="sonnet",
        temperature=0.7,
        reads={"aide_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        f"ai_sci_v2-improve-{stage_name}",
        [build_prompt, generate],
        inputs=[port("tree", "tree_state.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"tree_state.json", "aide_target.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _debug_package(stage_name: str) -> Package:
    """Repair a buggy node; debugging is stage-independent and runs cooler."""
    build_prompt = op(
        f"debug_prompt_{stage_name}",
        "srf.ops.aide.ops:build_debug_prompt",
        reads={"tree_state.json", "aide_target.json", "task.yaml"},
        writes={"aide_prompt.md"},
        notes="Prompt with the buggy node's code and its error output.",
    )
    generate = llm(
        f"debug_gen_{stage_name}",
        DEBUG_PROMPT,
        model="sonnet",
        temperature=0.5,
        reads={"aide_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        f"ai_sci_v2-debug-{stage_name}",
        [build_prompt, generate],
        inputs=[port("tree", "tree_state.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"tree_state.json", "aide_target.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _eval_package(stage_name: str) -> Package:
    """Score the candidate whichever branch produced it."""
    return single(
        op(
            f"eval_{stage_name}",
            "srf.ops.common.sandbox:run_eval",
            reads={"candidate.py", "task.yaml"},
            writes={"eval_result.json"},
            notes="Run the task's eval command on the candidate and record the score.",
        ),
        inputs=[port("candidate", "candidate.py", "text/x-python")],
        outputs=[port("result", "eval_result.json", "application/json")],
        requires={"candidate.py", "task.yaml"},
        produces={"eval_result.json"},
    )


def _update_package(stage_name: str) -> Package:
    """Fold the score into the tree the stages share."""
    return single(
        op(
            f"tree_update_{stage_name}",
            "srf.ops.aide.ops:update_tree",
            reads={"eval_result.json", "candidate.py", "aide_target.json", "tree_state.json"},
            writes=UPDATE_WRITES,
            notes="Add the candidate to the tree and promote it when it scores best.",
        ),
        inputs=[port("result", "eval_result.json", "application/json")],
        outputs=[port("tree", "tree_state.json", "application/json")],
        requires={"eval_result.json", "candidate.py", "aide_target.json", "tree_state.json"},
        produces=UPDATE_WRITES,
    )


def _stage_loop(stage_name: str) -> Package:
    """One stage: its own study loop over the shared tree."""
    action_gate = gate(
        f"action_gate_{stage_name}",
        "python -m srf.ops.aide.gate action",
        reads={"aide_action.txt"},
        gate_prompt="draft a new solution, improve the best node, or debug a buggy node.",
    )
    action = Conditional(
        action_gate,
        {
            "draft": _draft_package(stage_name),
            "improve": _improve_package(stage_name),
            "debug": _debug_package(stage_name),
        },
        name=f"ai_sci_v2-action-{stage_name}",
    )
    iteration = Sequential(
        _policy_package(stage_name),
        action,
        _eval_package(stage_name),
        _update_package(stage_name),
        name=f"ai_sci_v2-iter-{stage_name}",
    )
    return loop(
        iteration,
        budget_gate(f"budget_{stage_name}"),
        name=f"ai_sci_v2-stage-{stage_name}",
    )


def _transition_package(index: int) -> Package:
    """Advance the pipeline's stage counter between two loops."""
    return single(
        op(
            f"transition_{index}",
            "srf.ops.ai_sci.ops:stage_transition",
            reads={"ai_sci_state.json"},
            writes={"ai_sci_state.json"},
            notes="Close the finished stage and open the next one.",
        ),
        inputs=[port("state", "ai_sci_state.json", "application/json")],
        outputs=[port("state", "ai_sci_state.json", "application/json")],
        requires={"ai_sci_state.json"},
        produces={"ai_sci_state.json"},
    )


def build_ai_sci_v2_knobs() -> list[OptKnob]:
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_ai_sci_v2_memory() -> list[MemoryDeclaration]:
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_ai_sci_v2_workflow() -> Workflow:
    """Lower ai_sci_v2 to the flat DAG the spine executes."""
    pipeline: list[Package] = []
    for index, stage_name in enumerate(STAGE_NAMES):
        pipeline.append(_stage_loop(stage_name))
        if index < len(STAGE_NAMES) - 1:
            pipeline.append(_transition_package(index))
    root = Sequential(task_input(), seed_run(SEEDS), *pipeline, name="ai_sci_v2")
    return compile_mode("ai_sci_v2", declared(root, knobs=KNOBS, memory=MEMORY))
