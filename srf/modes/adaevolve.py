"""AdaEvolve mode — adaptive evolution with a meta-strategy switch.

Graph:
  task_input → seed_run → Loop:
    adaptive_sample → meta_gate_fn → meta_gate ──normal──▶ normal_prompt → normal_generate ─┐
                                              └──meta────▶ meta_prompt  → meta_generate   ─┤
                                                                                           ▼
                                                        join_adaevolve-strategy → sandbox_eval
                                                                                        │
                                                            archive_update ◀────────────┘
                                                                  │
                                       budget_check ◀─────────────┘
                                                    ──reloop──▶ adaptive_sample
                                                    ──proceed─▶ exit_adaevolve

``meta_gate`` is a switch, not a rewind: both outcomes continue the same
iteration along different branches, which rejoin at the conditional's join node
before evaluation. ``normal`` and ``meta`` are the evaluator's own verdict words.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    Conditional,
    Sequential,
    budget_gate,
    chain,
    compile_mode,
    declared,
    eval_step,
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

SYSTEM_PROMPT_NORMAL = (
    "You are AdaEvolve in NORMAL mode. Incrementally improve the solution. "
    "Output a single fenced code block."
)

SYSTEM_PROMPT_META = (
    "You are AdaEvolve in META-STRATEGY mode. The search is stagnating. "
    "Try a fundamentally different approach. Be creative and bold. "
    "Output a single fenced code block."
)

ARCHIVE_WRITES = {"population.json", "adaevolve_state.json", "best_solution.py"}

SEEDS = ("population.json", "adaevolve_state.json", "best_solution.py")
"""The mutable artifacts the loop reads or maintains, seeded before the first pass."""

KNOBS = [
    knob(
        "temperature",
        "threshold",
        0.7,
        [0.3, 0.5, 0.7, 0.9, 1.0],
        "normal_generate",
        "LLM sampling temperature",
    ),
    knob(
        "parent_selection",
        "prompt",
        "best",
        ["best", "epsilon_greedy", "power_law", "uniform"],
        "adaptive_sample",
        "Parent selection strategy",
    ),
    knob(
        "meta_temperature",
        "threshold",
        1.0,
        [0.8, 0.9, 1.0],
        "meta_generate",
        "Temperature for meta-strategy exploration",
    ),
]

MEMORY = [
    memory("adaevolve.population", "kv"),
    memory("adaevolve.meta", "log"),
]


def _sample_package():
    """Sample a parent with adaptive exploration, and measure stagnation."""
    return chain(
        "adaevolve-sample",
        [
            op(
                "adaptive_sample",
                "srf.ops.adaevolve.ops:adaptive_sample",
                reads={"population.json", "adaevolve_state.json"},
                writes={"selected_parent.json", "ada_stagnation.json"},
            )
        ],
        inputs=[port("population", "population.json", "application/json")],
        outputs=[port("parent", "selected_parent.json", "application/json")],
        requires={"population.json", "adaevolve_state.json"},
        produces={"selected_parent.json", "ada_stagnation.json"},
    )


def _verdict_package():
    """The deterministic pre-step that states whether the search is stagnating."""
    return single(
        op(
            "meta_gate_fn",
            "srf.ops.adaevolve.ops:meta_strategy_gate_fn",
            reads={"adaevolve_state.json"},
            writes={"meta_decision.txt"},
        ),
        inputs=[port("state", "adaevolve_state.json", "application/json")],
        outputs=[port("decision", "meta_decision.txt")],
        requires={"adaevolve_state.json"},
        produces={"meta_decision.txt"},
    )


def _normal_package():
    """An incremental step: one prompt built from the stagnation signal."""
    prompt = op(
        "normal_prompt",
        "srf.ops.adaevolve.ops:build_ada_prompt",
        reads={"selected_parent.json", "ada_stagnation.json", "task.yaml"},
        writes={"ada_prompt.md"},
    )
    generate = llm(
        "normal_generate",
        SYSTEM_PROMPT_NORMAL,
        temperature=0.7,
        reads={"ada_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "adaevolve-normal",
        [prompt, generate],
        inputs=[port("stagnation", "ada_stagnation.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"selected_parent.json", "ada_stagnation.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _meta_package():
    """A radical step: the same context, read as a mandate to change approach."""
    prompt = op(
        "meta_prompt",
        "srf.ops.adaevolve.ops:build_ada_prompt",
        reads={"selected_parent.json", "ada_stagnation.json", "task.yaml"},
        writes={"ada_prompt.md"},
    )
    generate = llm(
        "meta_generate",
        SYSTEM_PROMPT_META,
        temperature=1.0,
        reads={"ada_prompt.md"},
        writes={"candidate.py"},
    )
    return chain(
        "adaevolve-meta",
        [prompt, generate],
        inputs=[port("stagnation", "ada_stagnation.json", "application/json")],
        outputs=[port("candidate", "candidate.py", "text/x-python")],
        requires={"selected_parent.json", "ada_stagnation.json", "task.yaml"},
        produces={"candidate.py"},
    )


def _update_package():
    """Fold the scored candidate into the population and the run state."""
    return single(
        op(
            "archive_update",
            "srf.ops.adaevolve.ops:update_ada_archive",
            reads={
                "eval_result.json",
                "candidate.py",
                "selected_parent.json",
                "population.json",
            },
            writes=ARCHIVE_WRITES,
        ),
        inputs=[port("result", "eval_result.json", "application/json")],
        outputs=[port("solution", "best_solution.py", "text/x-python")],
        requires={"eval_result.json", "candidate.py", "selected_parent.json"},
        produces=ARCHIVE_WRITES,
    )


def build_adaevolve_knobs():
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_adaevolve_memory():
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_adaevolve_workflow() -> Workflow:
    """Lower adaevolve to the flat DAG the spine executes."""
    meta_gate = gate(
        "meta_gate",
        "python -m srf.ops.adaevolve.gate meta_gate",
        reads={"meta_decision.txt"},
        gate_prompt="take an incremental step, or a radical meta-strategy jump.",
    )
    strategy = Conditional(
        meta_gate,
        {"normal": _normal_package(), "meta": _meta_package()},
        name="adaevolve-strategy",
    )
    iteration = Sequential(
        _sample_package(),
        _verdict_package(),
        strategy,
        eval_step("sandbox_eval"),
        _update_package(),
        name="adaevolve-iteration",
    )
    study = loop(iteration, budget_gate(), name="adaevolve")
    root = Sequential(task_input(), seed_run(SEEDS), study, name="adaevolve")
    return compile_mode("adaevolve", declared(root, knobs=KNOBS, memory=MEMORY))
