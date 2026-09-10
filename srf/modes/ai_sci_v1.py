"""AI Scientist V1 mode — paper-writing loop.

Graph:
  task_input → seed_run → ideation → ideation_llm → Loop(ai_sci_v1):
    exp_prompt → exp_llm → sandbox_eval → exp_update
                                        │
                                        ▼
                        budget_check ──reloop──▶ exp_prompt
                                     ──proceed─▶ exit_ai_sci_v1
  → writeup → writeup_llm → review → review_llm

Four scientific stages: ideation, experimentation (the study loop), writeup, and
self-review. The loop is the only cycle; writeup and review run once, off the
best solution the loop left behind.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    MemoryDeclaration,
    OptKnob,
    Package,
    Sequential,
    budget_gate,
    chain,
    compile_mode,
    declared,
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

IDEATION_PROMPT = "You are AI Scientist V1 in the IDEATION stage. Generate research ideas."
EXPERIMENT_PROMPT = (
    "You are AI Scientist V1 in the EXPERIMENTATION stage. "
    "Implement and improve the solution iteratively. "
    "Output a single fenced code block."
)
WRITEUP_PROMPT = "You are AI Scientist V1. Write a structured report of your findings."
REVIEW_PROMPT = "You are AI Scientist V1. Review the quality of the solution."

KNOBS = [
    knob(
        "temperature",
        "threshold",
        0.7,
        [0.3, 0.5, 0.7, 0.9],
        "exp_llm",
        "LLM sampling temperature",
    ),
    knob(
        "experiment_budget",
        "threshold",
        20.0,
        [10.0, 20.0, 50.0],
        "budget_check",
        "Budget for experimentation stage",
    ),
]

SEEDS = ("ai_sci_state.json", "autoresearch_state.json", "best_solution.py")
"""The loop reads the best solution, and writeup/review read the run's state."""

MEMORY = [
    memory("ai_sci_v1.ideas", "log", "run"),
    memory("ai_sci_v1.writeup", "kv", "run"),
]

UPDATE_WRITES = {"autoresearch_state.json", "best_solution.py"}


def _ideation_package() -> Package:
    """Stage 1: turn the task into research ideas."""
    ideation = op(
        "ideation",
        "srf.ops.ai_sci.ops:ideation",
        reads={"task.yaml"},
        writes={"ideation_prompt.md"},
        notes="Prompt for 3-5 research ideas with benefit and risk.",
    )
    ideation_llm = llm(
        "ideation_llm",
        IDEATION_PROMPT,
        model="sonnet",
        temperature=0.9,
        reads={"ideation_prompt.md"},
        writes={"ideas.md"},
    )
    return chain(
        "ai_sci_v1-ideation",
        [ideation, ideation_llm],
        inputs=[port("task", "task.yaml", "application/yaml")],
        outputs=[port("ideas", "ideas.md", "text/markdown")],
        requires={"task.yaml"},
        produces={"ideas.md"},
    )


def _experiment_prompt_package() -> Package:
    """Stage 2a: prompt from the ideas and the best solution so far."""
    return single(
        op(
            "exp_prompt",
            "srf.ops.autoresearch.ops:build_optimization_prompt",
            reads={"ideas.md", "best_solution.py", "task.yaml"},
            writes={"optimize_prompt.md"},
            notes="Prompt with the current best code and the ideation findings.",
        ),
        inputs=[port("ideas", "ideas.md", "text/markdown")],
        outputs=[port("prompt", "optimize_prompt.md", "text/markdown")],
        requires={"ideas.md", "best_solution.py", "task.yaml"},
        produces={"optimize_prompt.md"},
    )


def _experiment_generate_package() -> Package:
    """Stage 2b: the iteration's candidate."""
    return single(
        llm(
            "exp_llm",
            EXPERIMENT_PROMPT,
            model="sonnet",
            temperature=0.7,
            reads={"optimize_prompt.md"},
            writes={"candidate.py"},
        ),
        inputs=[port("prompt", "optimize_prompt.md", "text/markdown")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"optimize_prompt.md"},
        produces={"candidate.py"},
    )


def _experiment_eval_package() -> Package:
    """Stage 2c: score the candidate with the task's own eval."""
    return single(
        op(
            "sandbox_eval",
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


def _experiment_update_package() -> Package:
    """Stage 2d: keep the candidate when it beats the best score."""
    return single(
        op(
            "exp_update",
            "srf.ops.autoresearch.ops:update_autoresearch",
            reads={"eval_result.json", "candidate.py"},
            writes=UPDATE_WRITES,
            notes="Count the eval and promote the candidate to best when it wins.",
        ),
        inputs=[port("result", "eval_result.json", "application/json")],
        outputs=[port("solution", "best_solution.py", "text/x-python")],
        requires={"eval_result.json", "candidate.py"},
        produces=UPDATE_WRITES,
    )


def _writeup_package() -> Package:
    """Stage 3: report the best solution the loop left behind."""
    writeup = op(
        "writeup",
        "srf.ops.ai_sci.ops:writeup",
        reads={"best_solution.py", "ai_sci_state.json"},
        writes={"writeup_prompt.md"},
        notes="Prompt for a structured report on the best solution.",
    )
    writeup_llm = llm(
        "writeup_llm",
        WRITEUP_PROMPT,
        model="sonnet",
        temperature=0.5,
        reads={"writeup_prompt.md"},
        writes={"writeup.md"},
    )
    return chain(
        "ai_sci_v1-writeup",
        [writeup, writeup_llm],
        inputs=[port("solution", "best_solution.py", "text/x-python")],
        outputs=[port("report", "writeup.md", "text/markdown")],
        requires={"best_solution.py", "ai_sci_state.json"},
        produces={"writeup.md"},
    )


def _review_package() -> Package:
    """Stage 4: self-assess the solution that the writeup describes."""
    review = op(
        "review",
        "srf.ops.ai_sci.ops:review",
        reads={"best_solution.py", "ai_sci_state.json"},
        writes={"review_prompt.md"},
        notes="Prompt for correctness, efficiency, novelty, and quality scores.",
    )
    review_llm = llm(
        "review_llm",
        REVIEW_PROMPT,
        model="sonnet",
        temperature=0.3,
        reads={"review_prompt.md"},
        writes={"review.md"},
    )
    return chain(
        "ai_sci_v1-review",
        [review, review_llm],
        inputs=[port("solution", "best_solution.py", "text/x-python")],
        outputs=[port("review", "review.md", "text/markdown")],
        requires={"best_solution.py", "ai_sci_state.json"},
        produces={"review.md"},
    )


def build_ai_sci_v1_knobs() -> list[OptKnob]:
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_ai_sci_v1_memory() -> list[MemoryDeclaration]:
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_ai_sci_v1_workflow() -> Workflow:
    """Lower ai_sci_v1 to the flat DAG the spine executes."""
    iteration = Sequential(
        _experiment_prompt_package(),
        _experiment_generate_package(),
        _experiment_eval_package(),
        _experiment_update_package(),
        name="ai_sci_v1-iteration",
    )
    study = loop(iteration, budget_gate(), name="ai_sci_v1")
    root = Sequential(
        task_input(),
        seed_run(SEEDS),
        _ideation_package(),
        study,
        _writeup_package(),
        _review_package(),
        name="ai_sci_v1",
    )
    return compile_mode("ai_sci_v1", declared(root, knobs=KNOBS, memory=MEMORY))
