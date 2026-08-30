"""Tests for AIDE mode (Issue #10)."""

import importlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from srf._factory_shim import Conditional, FnNode, GateNode, LLMNode, Loop, Package, Sequential
from srf.modes.aide import build_aide_knobs, build_aide_memory, build_aide_workflow
from tests.conftest import collect_nodes
from srf.ops.common.tree import TreeNode, TreeState, summarize_path


def test_workflow_structure():
    wf = build_aide_workflow()
    assert wf.name == "aide"
    assert isinstance(wf.root, Loop)
    body = wf.root.body
    assert isinstance(body, Sequential)
    assert len(body.children) == 4

    policy = body.children[0]
    assert isinstance(policy, FnNode)
    assert policy.name == "search_policy"

    action = body.children[1]
    assert isinstance(action, Conditional)
    assert len(action.branches) == 3
    assert "DRAFT" in action.branches
    assert "IMPROVE" in action.branches
    assert "DEBUG" in action.branches


def test_three_branch_conditional():
    wf = build_aide_workflow()
    cond = wf.root.body.children[1]
    assert isinstance(cond, Conditional)
    for key, branch in cond.branches.items():
        assert isinstance(branch, Package), f"Branch {key} is not a Package"


def test_knobs():
    knobs = build_aide_knobs()
    names = {k.name for k in knobs}
    assert "temperature" in names
    assert "debug_prob" in names
    for k in knobs:
        assert k.default in k.bounds


def test_memory_declarations():
    mem = build_aide_memory()
    assert len(mem) >= 1


def test_fn_nodes_resolve():
    wf = build_aide_workflow()
    fn_nodes = collect_nodes(wf.root, FnNode)
    for fn in fn_nodes:
        module_path, func_name = fn.callable_name.split(":")
        module = importlib.import_module(module_path)
        assert hasattr(module, func_name), f"{fn.callable_name} not importable"


def test_registry_discovers():
    from srf.registry import ModeRegistry
    registry = ModeRegistry()
    assert "aide" in registry.list_modes()


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


