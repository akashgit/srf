"""Shared test helpers for SRF's flat-DAG mode graphs."""

from __future__ import annotations

from typing import Any, Iterable

from factory.workflow.primitives import Node, Workflow


def nodes_of(workflow: Workflow, type_name: str) -> list[Node]:
    """Every node in the flat graph whose ``_type`` matches."""
    return [node for node in workflow.nodes.values() if type(node).__name__ == type_name]


def ids_of(workflow: Workflow, type_name: str) -> list[str]:
    """Sorted ids of every node of the given type."""
    return sorted(node.id for node in nodes_of(workflow, type_name))


def edges_from(workflow: Workflow, node_id: str) -> list[tuple[str, str | None]]:
    """Every outgoing edge of one node, as ``(target, condition)`` pairs."""
    return [
        (edge.target, str(edge.condition) if edge.condition is not None else None)
        for edge in workflow.edges
        if edge.source == node_id
    ]


def reloop_edges(workflow: Workflow) -> list[tuple[str, str]]:
    """Every ``reloop`` edge — the only cycle form the spine understands."""
    return [
        (edge.source, edge.target)
        for edge in workflow.edges
        if edge.condition is not None and str(edge.condition) == "reloop"
    ]


def node_ids(workflow: Workflow) -> set[str]:
    """The workflow's node ids."""
    return set(workflow.nodes)


def missing_writers(workflow: Workflow, ignores: Iterable[str] = ()) -> list[str]:
    """Reads that no ancestor of the reading node writes.

    Mirrors refactory's static data-dependency check, so a mode that only works
    because a back edge happens to supply a file still passes here.
    """
    ignored = set(ignores)
    problems: list[str] = []
    for node_id, node in workflow.nodes.items():
        if not node.reads:
            continue
        available: set[str] = set()
        for other_id, other in workflow.nodes.items():
            if other_id != node_id:
                available |= other.writes
        missing = set(node.reads) - available - ignored
        if missing:
            problems.append(f"{node_id} reads {sorted(missing)}")
    return problems


def as_dict(workflow: Workflow) -> dict[str, Any]:
    """The emitted ``graph.json`` payload."""
    return workflow.to_dict()
