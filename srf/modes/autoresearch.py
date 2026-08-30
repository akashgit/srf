"""AutoResearch mode — research-driven optimization.

DAG structure:
  Sequential(
    research_phase, research_llm,
    Loop(body=Sequential(optimize_prompt, optimize_llm, eval, update), gate=budget)
  )
"""

from __future__ import annotations

from srf._factory_shim import (
    Edge, FnNode, GateNode, LLMNode, Loop, MemoryDeclaration, OptKnob, Sequential, Workflow,
)

RESEARCH_PROMPT = (
    "You are a research synthesis agent. Analyze the task and available literature "
    "to identify promising optimization strategies."
)

OPTIMIZE_PROMPT = (
    "You are AutoResearch, a research-informed code optimizer. Use research findings "
    "to produce an improved solution. Output a single fenced code block."
)


def build_autoresearch_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.7,
                bounds=[0.3, 0.5, 0.7, 0.9], node_id="generate",
                description="LLM sampling temperature"),
        OptKnob(name="research_depth", kind="threshold", default=3.0,
                bounds=[1.0, 3.0, 5.0], node_id="research",
                description="Number of research iterations"),
    ]


def build_autoresearch_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="autoresearch.findings", kind="log", retention="run"),
    ]


def build_autoresearch_workflow() -> Workflow:
    research = FnNode(name="research_phase", callable_name="srf.ops.autoresearch.ops:research_phase",
                      reads={"task.yaml"}, writes={"research_prompt.md"})
    research_llm = LLMNode(name="research_llm", model="sonnet", temperature=0.5,
                           system_prompt=RESEARCH_PROMPT,
                           reads={"research_prompt.md"}, writes={"research_output.md"})

    opt_prompt = FnNode(name="optimize_prompt", callable_name="srf.ops.autoresearch.ops:build_optimization_prompt",
                        reads={"research_output.md", "best_solution.py", "task.yaml"}, writes={"optimize_prompt.md"})
    opt_llm = LLMNode(name="optimize_llm", model="sonnet", temperature=0.7,
                      system_prompt=OPTIMIZE_PROMPT, reads={"optimize_prompt.md"}, writes={"candidate.py"})
    evaluate = FnNode(name="sandbox_eval", callable_name="srf.ops.common.sandbox:run_eval",
                      reads={"candidate.py", "task.yaml"}, writes={"eval_result.json"})
    update = FnNode(name="update", callable_name="srf.ops.autoresearch.ops:update_autoresearch",
                    reads={"eval_result.json", "candidate.py"}, writes={"autoresearch_state.json", "best_solution.py"})

    budget_gate = GateNode(name="budget_check", evaluator_command="python -m srf.ops.common.budget check")
    opt_loop = Loop(name="optimize-loop",
                    body=Sequential(name="opt-iter", children=[opt_prompt, opt_llm, evaluate, update]),
                    gate=budget_gate, max_iterations=500)

    root = Sequential(name="autoresearch-main", children=[research, research_llm, opt_loop])

    return Workflow(name="autoresearch", root=root,
                    knobs=build_autoresearch_knobs(), memory=build_autoresearch_memory())
