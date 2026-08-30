"""AI Scientist V1 mode — paper-writing loop.

4-stage scientific pipeline:
  1. Ideation: generate research ideas
  2. Experimentation: iterative code optimization (Loop)
  3. Writeup: structured report generation
  4. Review: self-assessment

DAG structure:
  Sequential(ideation_llm, experiment_loop, writeup_llm, review_llm)
"""

from __future__ import annotations

from srf._factory_shim import (
    Edge, FnNode, GateNode, LLMNode, Loop, MemoryDeclaration, OptKnob, Sequential, Workflow,
)

IDEATION_PROMPT = "You are AI Scientist V1 in the IDEATION stage. Generate research ideas."
EXPERIMENT_PROMPT = (
    "You are AI Scientist V1 in the EXPERIMENTATION stage. "
    "Implement and improve the solution iteratively. "
    "Output a single fenced code block."
)
WRITEUP_PROMPT = "You are AI Scientist V1. Write a structured report of your findings."
REVIEW_PROMPT = "You are AI Scientist V1. Review the quality of the solution."


def build_ai_sci_v1_knobs() -> list[OptKnob]:
    return [
        OptKnob(name="temperature", kind="threshold", default=0.7,
                bounds=[0.3, 0.5, 0.7, 0.9], node_id="generate",
                description="LLM sampling temperature"),
        OptKnob(name="experiment_budget", kind="threshold", default=20.0,
                bounds=[10.0, 20.0, 50.0], node_id="experiment",
                description="Budget for experimentation stage"),
    ]


def build_ai_sci_v1_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="ai_sci_v1.ideas", kind="log", retention="run"),
        MemoryDeclaration(namespace="ai_sci_v1.writeup", kind="kv", retention="run"),
    ]


def build_ai_sci_v1_workflow() -> Workflow:
    # Stage 1: Ideation
    ideation = FnNode(name="ideation", callable_name="srf.ops.ai_sci.ops:ideation",
                      reads={"task.yaml"}, writes={"ideation_prompt.md"})
    ideation_llm = LLMNode(name="ideation_llm", model="sonnet", temperature=0.9,
                           system_prompt=IDEATION_PROMPT,
                           reads={"ideation_prompt.md"}, writes={"ideas.md"})

    # Stage 2: Experimentation Loop
    exp_prompt = FnNode(name="exp_prompt",
                        callable_name="srf.ops.autoresearch.ops:build_optimization_prompt",
                        reads={"ideas.md", "best_solution.py", "task.yaml"},
                        writes={"optimize_prompt.md"})
    exp_llm = LLMNode(name="exp_llm", model="sonnet", temperature=0.7,
                      system_prompt=EXPERIMENT_PROMPT,
                      reads={"optimize_prompt.md"}, writes={"candidate.py"})
    exp_eval = FnNode(name="sandbox_eval", callable_name="srf.ops.common.sandbox:run_eval",
                      reads={"candidate.py", "task.yaml"}, writes={"eval_result.json"})
    exp_update = FnNode(name="exp_update", callable_name="srf.ops.autoresearch.ops:update_autoresearch",
                        reads={"eval_result.json", "candidate.py"},
                        writes={"autoresearch_state.json", "best_solution.py"})

    budget_gate = GateNode(name="budget_check", evaluator_command="python -m srf.ops.common.budget check")
    exp_loop = Loop(name="experiment-loop",
                    body=Sequential(name="exp-iter", children=[exp_prompt, exp_llm, exp_eval, exp_update]),
                    gate=budget_gate, max_iterations=500)

    # Stage 3: Writeup
    writeup = FnNode(name="writeup", callable_name="srf.ops.ai_sci.ops:writeup",
                     reads={"best_solution.py", "ai_sci_state.json"}, writes={"writeup_prompt.md"})
    writeup_llm = LLMNode(name="writeup_llm", model="sonnet", temperature=0.5,
                          system_prompt=WRITEUP_PROMPT,
                          reads={"writeup_prompt.md"}, writes={"writeup.md"})

    # Stage 4: Review
    review = FnNode(name="review", callable_name="srf.ops.ai_sci.ops:review",
                    reads={"best_solution.py", "ai_sci_state.json"}, writes={"review_prompt.md"})
    review_llm = LLMNode(name="review_llm", model="sonnet", temperature=0.3,
                         system_prompt=REVIEW_PROMPT,
                         reads={"review_prompt.md"}, writes={"review.md"})

    root = Sequential(name="ai_sci_v1-pipeline",
                      children=[ideation, ideation_llm, exp_loop, writeup, writeup_llm, review, review_llm])

    return Workflow(name="ai_sci_v1", root=root,
                    knobs=build_ai_sci_v1_knobs(), memory=build_ai_sci_v1_memory())
