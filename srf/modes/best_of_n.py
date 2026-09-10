"""Best-of-N mode — IID sampling.

Graph:
  task_input → Fork(N samples) → Join → select_best
  each sample: build_prompt_i → generate_i → eval_i

Every branch declares its own files, so the N samples never share an artifact
and can be evaluated concurrently.
"""

from __future__ import annotations

from factory.workflow.primitives import Workflow

from srf.packaging import (
    Parallel,
    Sequential,
    chain,
    compile_mode,
    declared,
    knob,
    llm,
    memory,
    op,
    port,
    single,
    task_input,
)

SYSTEM_PROMPT = (
    "You are a code optimization agent. Given a task description and initial code, "
    "produce an improved solution. Output a single fenced code block."
)

N_CANDIDATES = 5

KNOBS = [
    knob(
        "n_candidates",
        "threshold",
        float(N_CANDIDATES),
        [3.0, 5.0, 10.0, 20.0],
        "fork_best_of_n-samples",
        "Number of independent candidates the fork fans out",
    ),
    knob(
        "temperature",
        "threshold",
        0.8,
        [0.5, 0.7, 0.8, 0.9, 1.0],
        "generate_0",
        "LLM sampling temperature",
    ),
]

MEMORY = [memory("best_of_n.candidates", "log")]

SELECT_WRITES = {"best_solution.py", "best_of_n_result.json"}


def _sample_branch(index: int):
    """One independent sample: build its prompt, generate, score."""
    prompt_name = f"candidate_prompt_{index}.md"
    candidate_name = f"candidate_{index}.py"
    prompt = op(
        f"build_prompt_{index}",
        "srf.ops.best_of_n.ops:build_candidate_prompt",
        reads={"task.yaml"},
        writes={prompt_name},
    )
    generate = llm(
        f"generate_{index}",
        SYSTEM_PROMPT,
        temperature=0.8,
        reads={prompt_name},
        writes={candidate_name},
    )
    evaluate = op(
        f"eval_{index}",
        "srf.ops.common.sandbox:run_eval",
        reads={candidate_name, "task.yaml"},
        writes={f"eval_result_{index}.json"},
    )
    return chain(
        f"best_of_n-sample-{index}",
        [prompt, generate, evaluate],
        inputs=[port("task", "task.yaml", "application/yaml")],
        outputs=[port("result", f"eval_result_{index}.json", "application/json")],
        requires={"task.yaml"},
        produces={candidate_name, f"eval_result_{index}.json"},
    )


def _select_package():
    reads = {f"eval_result_{i}.json" for i in range(N_CANDIDATES)}
    reads |= {f"candidate_{i}.py" for i in range(N_CANDIDATES)}
    return single(
        op(
            "select_best",
            "srf.ops.best_of_n.ops:select_best_candidate",
            reads=reads,
            writes=SELECT_WRITES,
        ),
        inputs=[port("results", "eval_result_0.json", "application/json")],
        outputs=[port("solution", "best_solution.py", "text/x-python")],
        requires=reads,
        produces=SELECT_WRITES,
    )


def build_best_of_n_knobs():
    """The knob declarations, for callers that only want the tunables."""
    return list(KNOBS)


def build_best_of_n_memory():
    """The memory declarations, for callers that only want the namespaces."""
    return list(MEMORY)


def build_best_of_n_workflow() -> Workflow:
    """Lower best_of_n to the flat DAG the spine executes."""
    samples = Parallel(
        *[_sample_branch(i) for i in range(N_CANDIDATES)],
        name="best_of_n-samples",
    )
    root = Sequential(
        task_input(),
        samples,
        _select_package(),
        name="best_of_n",
    )
    return compile_mode("best_of_n", declared(root, knobs=KNOBS, memory=MEMORY))
