"""Shared tree state for tree-search modes (AIDE, AI-Sci V2)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TreeNode:
    id: str
    code: str
    score: float = 0.0
    is_buggy: bool = False
    debug_depth: int = 0
    parent_id: str | None = None
    children_ids: list[str] = field(default_factory=list)
    terminal_output: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    action: str = "draft"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "code": self.code, "score": self.score,
            "is_buggy": self.is_buggy, "debug_depth": self.debug_depth,
            "parent_id": self.parent_id, "children_ids": self.children_ids,
            "terminal_output": self.terminal_output, "metrics": self.metrics,
            "action": self.action,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TreeNode":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TreeState:
    nodes: dict[str, TreeNode] = field(default_factory=dict)
    best_id: str | None = None
    best_score: float = 0.0

    def add_node(self, node: TreeNode) -> bool:
        self.nodes[node.id] = node
        if node.parent_id and node.parent_id in self.nodes:
            parent = self.nodes[node.parent_id]
            if node.id not in parent.children_ids:
                parent.children_ids.append(node.id)
        is_new_best = node.score > self.best_score and not node.is_buggy
        if is_new_best:
            self.best_score = node.score
            self.best_id = node.id
        return is_new_best

    def get_best(self) -> TreeNode | None:
        if self.best_id:
            return self.nodes.get(self.best_id)
        return None

    def get_buggy_nodes(self) -> list[TreeNode]:
        return [n for n in self.nodes.values() if n.is_buggy]

    def get_path_to_root(self, node_id: str) -> list[TreeNode]:
        path = []
        current = node_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            node = self.nodes.get(current)
            if node is None:
                break
            path.append(node)
            current = node.parent_id
        return list(reversed(path))

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "best_id": self.best_id,
            "best_score": self.best_score,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TreeState":
        state = cls()
        state.best_id = d.get("best_id")
        state.best_score = d.get("best_score", 0.0)
        for nid, ndata in d.get("nodes", {}).items():
            state.nodes[nid] = TreeNode.from_dict(ndata)
        return state

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str))

    @classmethod
    def load(cls, path: Path) -> "TreeState":
        if not path.exists():
            return cls()
        return cls.from_dict(json.loads(path.read_text()))


def summarize_path(tree_state: TreeState, node_id: str, max_entries: int = 5) -> str:
    """Σ(T): bounded-length summary of root-to-node path.

    Keeps context manageable regardless of tree depth.
    """
    path = tree_state.get_path_to_root(node_id)
    if not path:
        return "No path found."

    if len(path) <= max_entries:
        entries = path
    else:
        entries = [path[0]] + path[-(max_entries - 1):]

    parts = []
    for i, node in enumerate(entries):
        status = "buggy" if node.is_buggy else f"score={node.score:.4f}"
        code_preview = node.code[:200] if node.code else "(empty)"
        parts.append(
            f"### Step {i+1} ({node.action}, {status})\n"
            f"```python\n{code_preview}\n```"
        )
        if node.terminal_output:
            parts.append(f"Output: {node.terminal_output[:200]}")

    if len(path) > max_entries:
        skipped = len(path) - max_entries
        parts.insert(1, f"... ({skipped} intermediate steps omitted) ...")

    return "\n\n".join(parts)
