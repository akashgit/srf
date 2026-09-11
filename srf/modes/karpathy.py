"""Karpathy mode — Claude Code agent with tool access.

Graph:
  task_input → seed_run → Loop:
    build_prompt → agent → sandbox_eval → update
                                            │
                                            ▼
                      budget_check ──reloop──▶ build_prompt
                                   ──proceed─▶ exit

The most autonomous mode: one tool-using agent node per iteration reads the
current best program plus its last evaluation feedback, then writes a candidate
that the update step folds back into ``best_solution.py``.
"""

from __future__ import annotations

from factory.workflow.primitives import AgentRole, Workflow

from srf.packaging import (
    MemoryDeclaration,
    OptKnob,
    Sequential,
    agent,
    budget_gate,
    compile_mode,
    declared,
    eval_step,
    knob,
    loop,
    memory,
    op,
    seed_run,
    single,
    task_input,
)

AGENT_SYSTEM_PROMPT = (
    "You are an autonomous code optimization agent (inspired by Karpathy's approach). "
    "You observe evaluation output, reason about what to change, and iterate. "
    "Think step by step. Output a single fenced code block with the complete solution."
)

KNOBS: list[OptKnob] = [
    knob(
        "temperature",
        "threshold",
        0.7,
        [0.3, 0.5, 0.7, 0.9],
        "agent",
        "LLM sampling temperature",
    ),
    knob(
        "max_turns",
        "threshold",
        10.0,
        [5.0, 10.0, 20.0, 50.0],
        "agent",
        "Maximum agent turns per iteration",
    ),
]

SEEDS = ("best_solution.py", "eval_result.json")
"""``build_prompt`` reads the incumbent and its last feedback on the first pass."""

MEMORY: list[MemoryDeclaration] = [memory("karpathy.history", "log")]

UPDATE_WRITES = {"karpathy_state.json", "best_solution.py"}


def _iteration_package():
    """One iteration: prompt the agent with feedback, then score and record it."""
    prompt = single(
        op(
            "build_prompt",
            "srf.ops.karpathy.ops:build_agent_prompt",
            reads={"best_solution.py", "eval_result.json", "task.yaml"},
            writes={"agent_prompt.md"},
        ),
        requires={"best_solution.py", "eval_result.json", "task.yaml"},
        produces={"agent_prompt.md"},
    )
    agent_node = single(
        agent(
            "agent",
            AGENT_SYSTEM_PROMPT,
            role=AgentRole.BUILDER,
            max_iterations=10,
            reads={"agent_prompt.md"},
            writes={"candidate.py"},
        ),
        requires={"agent_prompt.md"},
        produces={"candidate.py"},
    )
    update = single(
        op(
            "update",
            "srf.ops.karpathy.ops:update_karpathy_state",
            reads={"eval_result.json", "candidate.py"},
            writes=UPDATE_WRITES,
        ),
        requires={"eval_result.json", "candidate.py"},
        produces=UPDATE_WRITES,
    )
    return Sequential(
        prompt,
        agent_node,
        eval_step("sandbox_eval"),
        update,
        name="karpathy-iteration",
    )


def build_karpathy_knobs() -> list[OptKnob]:
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_karpathy_memory() -> list[MemoryDeclaration]:
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_karpathy_workflow() -> Workflow:
    """Lower karpathy to the flat DAG the spine executes."""
    study = loop(_iteration_package(), budget_gate(), name="karpathy")
    root = Sequential(task_input(), seed_run(SEEDS), study, name="karpathy")
    return compile_mode("karpathy", declared(root, knobs=KNOBS, memory=MEMORY))
