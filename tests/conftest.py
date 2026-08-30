"""Shared test helpers."""

from __future__ import annotations


def collect_nodes(node, node_type):
    """Recursively collect all nodes of a given type from a DAG."""
    found = []
    if isinstance(node, node_type):
        found.append(node)
    if hasattr(node, "children"):
        for child in node.children:
            found.extend(collect_nodes(child, node_type))
    if hasattr(node, "nodes"):
        for n in node.nodes:
            found.extend(collect_nodes(n, node_type))
    if hasattr(node, "body") and node.body:
        found.extend(collect_nodes(node.body, node_type))
    if hasattr(node, "branches"):
        for branch in node.branches.values():
            found.extend(collect_nodes(branch, node_type))
    return found
