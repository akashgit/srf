"""Karpathy mode — Claude Code agent with tool access.

The most autonomous mode: a single agent with iterative tool use.

DAG structure:
  Loop(body=Sequential(build_prompt, AgentNode, eval, update), gate=budget)
"""

from __future__ import annotations

from srf._factory_shim import (
    AgentNode, FnNode, GateNode, Loop, MemoryDeclaration, OptKnob, Sequential, Workflow,
)

AGENT_SYSTEM_PROMPT = (
    "You are an autonomous code optimization agent (inspired by Karpathy's approach). "
    "You observe evaluation output, reason about what to change, and iterate. "
    "Think step by step. Output a single fenced code block with the complete solution."
)


def build_karpathy_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.7,
                bounds=[0.3, 0.5, 0.7, 0.9], node_id="agent",
                description="LLM sampling temperature"),
        OptKnob(name="max_turns", kind="threshold", default=10.0,
                bounds=[5.0, 10.0, 20.0, 50.0], node_id="agent",
                description="Maximum agent turns per iteration"),
    ]


def build_karpathy_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="karpathy.history", kind="log", retention="run"),
    ]


def build_karpathy_workflow() -> Workflow:
    prompt = FnNode(name="build_prompt", callable_name="srf.ops.karpathy.ops:build_agent_prompt",
                    reads={"best_solution.py", "eval_result.json", "task.yaml"},
                    writes={"agent_prompt.md"})
    agent = AgentNode(name="agent", model="sonnet", system_prompt=AGENT_SYSTEM_PROMPT,
                      max_turns=10, reads={"agent_prompt.md"}, writes={"candidate.py"})
    evaluate = FnNode(name="sandbox_eval", callable_name="srf.ops.common.sandbox:run_eval",
                      reads={"candidate.py", "task.yaml"}, writes={"eval_result.json"})
    update = FnNode(name="update", callable_name="srf.ops.karpathy.ops:update_karpathy_state",
                    reads={"eval_result.json", "candidate.py"},
                    writes={"karpathy_state.json", "best_solution.py"})

    budget_gate = GateNode(name="budget_check", evaluator_command="python -m srf.ops.common.budget check")
    iteration = Sequential(name="karpathy-iteration", children=[prompt, agent, evaluate, update])
    loop = Loop(name="karpathy", body=iteration, gate=budget_gate, max_iterations=500)

    return Workflow(name="karpathy", root=loop, knobs=build_karpathy_knobs(), memory=build_karpathy_memory())
