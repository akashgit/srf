"""AutoScientists mode — multi-agent team.

Graph:
  task_input → Fork(N scientists) → Join → merge_prompt → merge_generate
             → sandbox_eval → update
  each scientist: scientist_prompt_i → scientist_gen_i → scientist_eval_i

N independent scientists attack the problem in parallel, each with its own prompt
file, its own ``scientist_i.py`` and its own ``scientist_result_i.json``; a merge
agent then combines their insights into a single candidate, which is scored and
recorded. Per-branch files are what let the fork run concurrently.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    MemoryDeclaration,
    OptKnob,
    Parallel,
    Sequential,
    chain,
    compile_mode,
    declared,
    eval_step,
    knob,
    llm,
    memory,
    op,
    port,
    single,
    task_input,
)

SCIENTIST_PROMPT = (
    "You are an independent scientist agent. Generate a creative and unique solution. "
    "Output a single fenced code block."
)

MERGE_PROMPT = (
    "You are a merge agent. Combine the best insights from multiple scientists' solutions. "
    "Output a single fenced code block."
)

N_SCIENTISTS = 3

KNOBS: list[OptKnob] = [
    knob(
        "n_scientists",
        "threshold",
        3.0,
        [2.0, 3.0, 5.0],
        "fork_autoscientists-scientists",
        "Number of parallel scientist agents",
    ),
    knob(
        "temperature",
        "threshold",
        0.9,
        [0.7, 0.8, 0.9, 1.0],
        "scientist_gen_0",
        "LLM sampling temperature",
    ),
]

MEMORY: list[MemoryDeclaration] = [memory("autoscientists.solutions", "log")]

UPDATE_WRITES = {"autoscientists_state.json", "best_solution.py"}


def _scientist_package(index: int):
    """One scientist: its own prompt, its own solution, its own score."""
    prompt_name = f"scientist_prompt_{index}.md"
    prompt = op(
        f"scientist_prompt_{index}",
        "srf.ops.autoscientists.ops:build_scientist_prompt",
        reads={"task.yaml"},
        writes={prompt_name},
    )
    generate = llm(
        f"scientist_gen_{index}",
        SCIENTIST_PROMPT,
        temperature=0.9,
        reads={prompt_name},
        writes={f"scientist_{index}.py"},
    )
    evaluate = op(
        f"scientist_eval_{index}",
        "srf.ops.common.sandbox:run_eval",
        reads={f"scientist_{index}.py", "task.yaml"},
        writes={f"scientist_result_{index}.json"},
    )
    return chain(
        f"autoscientists-scientist-{index}",
        [prompt, generate, evaluate],
        inputs=[port("task", "task.yaml", "application/yaml")],
        outputs=[port("result", f"scientist_result_{index}.json", "application/json")],
        requires={"task.yaml"},
        produces={prompt_name, f"scientist_{index}.py", f"scientist_result_{index}.json"},
    )


def _merge_package():
    """Combine every scientist's solution, then score and record the merge."""
    reads = {f"scientist_{i}.py" for i in range(N_SCIENTISTS)} | {
        f"scientist_result_{i}.json" for i in range(N_SCIENTISTS)
    }
    merge_prompt = single(
        op(
            "merge_prompt",
            "srf.ops.autoscientists.ops:build_merge_prompt",
            reads=reads,
            writes={"merge_prompt.md"},
        ),
        requires=reads,
        produces={"merge_prompt.md"},
    )
    merge_generate = single(
        llm(
            "merge_generate",
            MERGE_PROMPT,
            temperature=0.7,
            reads={"merge_prompt.md"},
            writes={"candidate.py"},
        ),
        requires={"merge_prompt.md"},
        produces={"candidate.py"},
    )
    update = single(
        op(
            "update",
            "srf.ops.autoscientists.ops:update_autoscientists",
            reads={"eval_result.json", "candidate.py"},
            writes=UPDATE_WRITES,
        ),
        requires={"eval_result.json", "candidate.py"},
        produces=UPDATE_WRITES,
    )
    return Sequential(
        merge_prompt,
        merge_generate,
        eval_step("sandbox_eval"),
        update,
        name="autoscientists-merge",
    )


def build_autoscientists_knobs() -> list[OptKnob]:
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_autoscientists_memory() -> list[MemoryDeclaration]:
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_autoscientists_workflow() -> Workflow:
    """Lower autoscientists to the flat DAG the spine executes."""
    scientists = Parallel(
        *[_scientist_package(i) for i in range(N_SCIENTISTS)],
        name="autoscientists-scientists",
    )
    root = Sequential(task_input(), scientists, _merge_package(), name="autoscientists")
    return compile_mode("autoscientists", declared(root, knobs=KNOBS, memory=MEMORY))
