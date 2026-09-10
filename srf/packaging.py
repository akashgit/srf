"""Compose SRF mode graphs from refactory's Package operators.

SRF is a **pure package**: it declares graphs (semantics) and deterministic ops.
The DSH workflow spine is the only runtime, so nothing here executes a graph.
Each mode builder returns a flat-DAG ``Workflow`` — refactory's IR — which
``Workflow.to_dict()`` serializes to ``graph.json`` and the spine consumes.

A mode is written as a composition of ``Package``s, and
:func:`compile_mode` lowers that composition to the flat DAG (nodes + labelled
edges). Loops become a ``reloop`` edge from a gate back to the body entry, which
is the only cycle the spine understands.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from factory.workflow.package import (  # noqa: F401  (re-exported for mode modules)
    Conditional,
    JoinStrategy,
    Loop,
    MemoryDeclaration,
    OptKnob,
    Package,
    Parallel,
    Port,
    Sequential,
    StateContract,
)
from factory.workflow.primitives import (
    AgentNode,
    AgentRole,
    Edge,
    FnNode,
    GateNode,
    LLMNode,
    Node,
    Workflow,
)

# ── node builders ──────────────────────────────────────────────────

DEFAULT_GATE_ITERATIONS = 500
"""Reloop cap for a budget-gated loop. The budget gate ends the loop in practice."""


def op(
    node_id: str,
    callable_name: str,
    *,
    reads: Iterable[str] = (),
    writes: Iterable[str] = (),
    notes: str = "",
) -> FnNode:
    """A deterministic op, named as ``srf.ops.<module>:<function>``.

    The node carries both the semantic ``callable_name`` and the ``command`` the
    runtime executes: ``python -m srf.ops.run <callable_name>``. The adapter
    (`srf/ops/run.py`) rebuilds the context the op expects from the node
    declaration and the run's environment.
    """
    return FnNode(
        id=node_id,
        callable_name=callable_name,
        command=f"python -m srf.ops.run {callable_name}",
        reads=set(reads),
        writes=set(writes),
        notes=notes,
    )


def command(
    node_id: str,
    shell_command: str,
    *,
    reads: Iterable[str] = (),
    writes: Iterable[str] = (),
    notes: str = "",
) -> FnNode:
    """A deterministic shell step, run by the runtime as a subprocess."""
    return FnNode(
        id=node_id,
        command=shell_command,
        reads=set(reads),
        writes=set(writes),
        notes=notes,
    )


def llm(
    node_id: str,
    system_prompt: str,
    *,
    model: str = "sonnet",
    temperature: float = 0.7,
    reads: Iterable[str] = (),
    writes: Iterable[str] = (),
    max_turns: int = 10,
) -> LLMNode:
    """A one-shot LLM call that turns its ``reads`` into its ``writes``."""
    return LLMNode(
        id=node_id,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        reads=set(reads),
        writes=set(writes),
        max_turns=max_turns,
    )


def agent(
    node_id: str,
    prompt_template: str,
    *,
    role: AgentRole = AgentRole.BUILDER,
    model: str = "sonnet",
    max_iterations: int = 10,
    reads: Iterable[str] = (),
    writes: Iterable[str] = (),
) -> AgentNode:
    """A tool-using agent node — the spine runs it as a content subagent."""
    return AgentNode(
        id=node_id,
        role=role,
        model=model,
        prompt_template=prompt_template,
        max_iterations=max_iterations,
        reads=set(reads),
        writes=set(writes),
    )


def gate(
    node_id: str,
    evaluator_command: str,
    *,
    reads: Iterable[str] = (),
    gate_prompt: str = "",
    max_iterations: int | None = None,
) -> GateNode:
    """A gate whose verdict comes from a deterministic subprocess."""
    return GateNode(
        id=node_id,
        evaluator_type="fn",
        evaluator_command=evaluator_command,
        gate_prompt=gate_prompt,
        reads=set(reads),
        max_iterations=max_iterations,
    )


def budget_gate(node_id: str = "budget_check") -> GateNode:
    """The loop terminator: reloop while evals remain, proceed once spent."""
    return gate(
        node_id,
        "python -m srf.ops.common.budget check",
        reads={"budget_state.json"},
        gate_prompt="reloop while the eval budget is unspent, proceed once it is spent.",
        max_iterations=DEFAULT_GATE_ITERATIONS,
    )


# ── package builders ───────────────────────────────────────────────


def knob(
    name: str,
    kind: str,
    default: str | float,
    bounds: Sequence[str | float],
    node_id: str,
    description: str = "",
) -> OptKnob:
    """An optimizer-tunable parameter, bound to the node it configures."""
    return OptKnob(
        name=name,
        kind=kind,  # type: ignore[arg-type]
        default=default,
        bounds=list(bounds),
        node_id=node_id,
        description=description,
    )


def memory(namespace: str, kind: str, retention: str = "run") -> MemoryDeclaration:
    """A declared persistent namespace."""
    return MemoryDeclaration(
        namespace=namespace,
        kind=kind,  # type: ignore[arg-type]
        retention=retention,  # type: ignore[arg-type]
    )


def port(name: str, artifact_path: str, media_type: str = "text/markdown") -> Port:
    """A named artifact slot on a package interface."""
    return Port(name=name, artifact_path=artifact_path, media_type=media_type)


def chain(
    name: str,
    nodes: Sequence[Node],
    *,
    edges: Sequence[Edge] | None = None,
    knobs: Sequence[OptKnob] = (),
    memory: Sequence[MemoryDeclaration] = (),
    inputs: Sequence[Port] = (),
    outputs: Sequence[Port] = (),
    requires: Iterable[str] = (),
    produces: Iterable[str] = (),
    description: str = "",
) -> Package:
    """One package holding ``nodes`` wired in order unless ``edges`` overrides.

    Every node needs a globally unique id: compositions merge node dictionaries
    and refuse collisions, which is what keeps a lowered DAG unambiguous.
    """
    if not nodes:
        raise ValueError(f"package '{name}' has no nodes")
    ordered = [node.id for node in nodes]
    wiring = list(edges) if edges is not None else [
        Edge(source=source, target=target)
        for source, target in zip(ordered, ordered[1:])
    ]
    graph = Workflow(
        name=name,
        nodes={node.id: node for node in nodes},
        edges=wiring,
        start_node=ordered[0],
    )
    return Package(
        name=name,
        description=description,
        inputs=list(inputs),
        outputs=list(outputs),
        contract=StateContract(requires=frozenset(requires), produces=frozenset(produces)),
        graph=graph,
        entry_node=ordered[0],
        exit_node=ordered[-1],
        knobs=list(knobs),
        memory=list(memory),
    )


def single(node: Node, **kwargs: Any) -> Package:
    """A package wrapping exactly one node."""
    return chain(getattr(node, "id"), [node], **kwargs)


TASK_FILES = ("task.yaml", "eval.py", "initial.py", "knobs.json", "budget_state.json")
"""The working set the entry node writes: the problem, its eval, and run settings."""


def task_input(node_id: str = "task_input") -> Package:
    """The graph's entry: materialize the problem and run settings.

    Every mode starts here, so the working set (``task.yaml`` plus the task's own
    ``eval.py`` / ``initial.py``, the resolved ``knobs.json``, and the initial
    ``budget_state.json`` the budget gate reads) exists before any node reads it.
    """
    return single(
        command(
            node_id,
            "python -m srf.ops.common.task_input",
            writes=TASK_FILES,
            notes="Materialize the selected task into the work directory.",
        ),
        outputs=[port("task", "task.yaml", "application/yaml")],
        produces=TASK_FILES,
    )


def seed_run(files: Iterable[str], node_id: str = "seed_run") -> Package:
    """The graph's second entry: give the search its starting point.

    The names are listed on the command line as well as in ``writes``, so the
    declared output set and the seeder's outputs cannot drift apart. The seeder
    only creates files that are absent, so it is safe on a resumed run.
    """
    ordered = sorted(set(files))
    if not ordered:
        raise ValueError("seed_run needs at least one file")
    return single(
        command(
            node_id,
            "python -m srf.ops.common.seed " + " ".join(ordered),
            writes=set(ordered),
            notes="Seed the run's population, tree, and per-mode state files.",
        ),
        produces=set(ordered),
    )


def eval_step(
    node_id: str,
    *,
    candidate: str = "candidate.py",
    result: str = "eval_result.json",
) -> Package:
    """Score a candidate with the task's own ``eval.py``, in the sandbox."""
    return single(
        op(
            node_id,
            "srf.ops.common.sandbox:run_eval",
            reads={candidate, "task.yaml"},
            writes={result},
            notes="Run the task's eval command on the candidate and record the score.",
        ),
        inputs=[port("candidate", candidate, "text/x-python")],
        outputs=[port("result", result, "application/json")],
        requires={candidate, "task.yaml"},
        produces={result},
    )


def loop(body: Package, gate_node: GateNode, *, name: str) -> Package:
    """Wrap ``body`` in the study loop: run it, then let the gate decide."""
    return Loop(body, gate_node, max_iterations=gate_node.max_iterations or DEFAULT_GATE_ITERATIONS, name=name)


def declared(
    package: Package,
    *,
    knobs: Sequence[OptKnob] = (),
    memory: Sequence[MemoryDeclaration] = (),
) -> Package:
    """Attach a mode's knobs and memory declarations to its composed package."""
    return package.model_copy(update={"knobs": list(knobs), "memory": list(memory)})


def compile_mode(name: str, root: Package, *, terminal: bool = True) -> Workflow:
    """Lower a composition to the flat-DAG ``Workflow`` the spine executes."""
    workflow = root.compile()
    workflow.name = name
    workflow.terminal = terminal
    return workflow


def all_nodes(workflow: Workflow) -> Mapping[str, Node]:
    """The workflow's node table."""
    return workflow.nodes
