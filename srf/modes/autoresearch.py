"""AutoResearch mode — research-driven optimization.

Graph:
  task_input → seed_run → research_phase → research_llm → Loop:
    optimize_prompt → optimize_llm → sandbox_eval → update
                                                        │
                                                        ▼
                                  budget_check ──reloop──▶ optimize_prompt
                                               ──proceed─▶ exit

The research phase runs once and writes ``research_output.md``; every iteration
then conditions its optimization prompt on those findings and folds the accepted
candidate back into ``best_solution.py``.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    MemoryDeclaration,
    OptKnob,
    Sequential,
    budget_gate,
    chain,
    compile_mode,
    declared,
    eval_step,
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

RESEARCH_PROMPT = (
    "You are a research synthesis agent. Analyze the task and available literature "
    "to identify promising optimization strategies."
)

OPTIMIZE_PROMPT = (
    "You are AutoResearch, a research-informed code optimizer. Use research findings "
    "to produce an improved solution. Output a single fenced code block."
)

KNOBS: list[OptKnob] = [
    knob(
        "temperature",
        "threshold",
        0.7,
        [0.3, 0.5, 0.7, 0.9],
        "optimize_llm",
        "LLM sampling temperature",
    ),
    knob(
        "research_depth",
        "threshold",
        3.0,
        [1.0, 3.0, 5.0],
        "research_phase",
        "Number of research iterations",
    ),
]

SEEDS = ("best_solution.py",)
"""The optimization prompt reads the incumbent on the loop's first pass."""

MEMORY: list[MemoryDeclaration] = [memory("autoresearch.findings", "log")]

UPDATE_WRITES = {"autoresearch_state.json", "best_solution.py"}


def _research_package():
    """Synthesize the literature once, before the optimization loop starts."""
    research = op(
        "research_phase",
        "srf.ops.autoresearch.ops:research_phase",
        reads={"task.yaml"},
        writes={"research_prompt.md"},
    )
    research_llm = llm(
        "research_llm",
        RESEARCH_PROMPT,
        temperature=0.5,
        reads={"research_prompt.md"},
        writes={"research_output.md"},
    )
    return chain(
        "autoresearch-research",
        [research, research_llm],
        inputs=[port("task", "task.yaml", "application/yaml")],
        outputs=[port("findings", "research_output.md")],
        requires={"task.yaml"},
        produces={"research_prompt.md", "research_output.md"},
    )


def _iteration_package():
    """One iteration: research-informed optimization, scored and recorded."""
    optimize_prompt = single(
        op(
            "optimize_prompt",
            "srf.ops.autoresearch.ops:build_optimization_prompt",
            reads={"research_output.md", "best_solution.py", "task.yaml"},
            writes={"optimize_prompt.md"},
        ),
        requires={"research_output.md", "best_solution.py", "task.yaml"},
        produces={"optimize_prompt.md"},
    )
    optimize_llm = single(
        llm(
            "optimize_llm",
            OPTIMIZE_PROMPT,
            temperature=0.7,
            reads={"optimize_prompt.md"},
            writes={"candidate.py"},
        ),
        requires={"optimize_prompt.md"},
        produces={"candidate.py"},
    )
    update = single(
        op(
            "update",
            "srf.ops.autoresearch.ops:update_autoresearch",
            reads={"eval_result.json", "candidate.py"},
            writes=UPDATE_WRITES,
        ),
        requires={"eval_result.json", "candidate.py"},
        produces=UPDATE_WRITES,
    )
    return Sequential(
        optimize_prompt,
        optimize_llm,
        eval_step("sandbox_eval"),
        update,
        name="autoresearch-iteration",
    )


def build_autoresearch_knobs() -> list[OptKnob]:
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_autoresearch_memory() -> list[MemoryDeclaration]:
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_autoresearch_workflow() -> Workflow:
    """Lower autoresearch to the flat DAG the spine executes."""
    study = loop(_iteration_package(), budget_gate(), name="autoresearch")
    root = Sequential(
        task_input(),
        seed_run(SEEDS),
        _research_package(),
        study,
        name="autoresearch",
    )
    return compile_mode("autoresearch", declared(root, knobs=KNOBS, memory=MEMORY))
