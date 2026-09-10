"""Tests for AIDE mode (Issue #10)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from srf.modes.aide import build_aide_knobs, build_aide_memory, build_aide_workflow
from srf.ops.common.tree import TreeNode, TreeState, summarize_path


def test_tree_node_roundtrip():
    node = TreeNode(id="n1", code="x=1", score=0.5, is_buggy=False, action="draft")
    d = node.to_dict()
    restored = TreeNode.from_dict(d)
    assert restored.id == "n1"
    assert restored.score == 0.5


def test_tree_state_add_and_best():
    state = TreeState()
    n1 = TreeNode(id="n1", code="x=1", score=0.3)
    n2 = TreeNode(id="n2", code="x=2", score=0.7, parent_id="n1")
    state.add_node(n1)
    is_new = state.add_node(n2)
    assert is_new
    assert state.best_id == "n2"
    assert state.best_score == 0.7
    assert "n2" in state.nodes["n1"].children_ids


def test_tree_state_save_load(tmp_path):
    state = TreeState()
    state.add_node(TreeNode(id="n1", code="x=1", score=0.5))
    state.save(tmp_path / "tree.json")
    loaded = TreeState.load(tmp_path / "tree.json")
    assert "n1" in loaded.nodes
    assert loaded.nodes["n1"].score == 0.5


def test_summarize_path():
    state = TreeState()
    for i in range(10):
        state.add_node(TreeNode(
            id=f"n{i}", code=f"x={i}", score=i * 0.1,
            parent_id=f"n{i-1}" if i > 0 else None, action="improve",
        ))
    summary = summarize_path(state, "n9", max_entries=3)
    assert "Step 1" in summary
    assert "omitted" in summary


def test_get_buggy_nodes():
    state = TreeState()
    state.add_node(TreeNode(id="n1", code="x=1", score=0.0, is_buggy=True))
    state.add_node(TreeNode(id="n2", code="x=2", score=0.5, is_buggy=False))
    buggy = state.get_buggy_nodes()
    assert len(buggy) == 1
    assert buggy[0].id == "n1"


def test_get_path_to_root():
    state = TreeState()
    state.add_node(TreeNode(id="root", code="x=0", score=0.1))
    state.add_node(TreeNode(id="child", code="x=1", score=0.3, parent_id="root"))
    state.add_node(TreeNode(id="grandchild", code="x=2", score=0.5, parent_id="child"))
    path = state.get_path_to_root("grandchild")
    assert [n.id for n in path] == ["root", "child", "grandchild"]


