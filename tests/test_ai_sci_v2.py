"""Tests for AI Scientist V2 mode (Issue #11)."""

import importlib

from srf._factory_shim import Conditional, FnNode, LLMNode, Loop, Package, Sequential
from srf.modes.ai_sci_v2 import build_ai_sci_v2_knobs, build_ai_sci_v2_memory, build_ai_sci_v2_workflow
from tests.conftest import collect_nodes


def test_workflow_structure():
    wf = build_ai_sci_v2_workflow()
    assert wf.name == "ai_sci_v2"
    assert isinstance(wf.root, Sequential)
    # 4 stages + 3 transitions = 7 children
    assert len(wf.root.children) == 7


def test_four_stage_loops():
    wf = build_ai_sci_v2_workflow()
    loops = [c for c in wf.root.children if isinstance(c, Loop)]
    assert len(loops) == 4
    for loop in loops:
        assert isinstance(loop.body, Sequential)


def test_each_stage_has_conditional():
    wf = build_ai_sci_v2_workflow()
    loops = [c for c in wf.root.children if isinstance(c, Loop)]
    for loop in loops:
        conditionals = [c for c in loop.body.children if isinstance(c, Conditional)]
        assert len(conditionals) == 1
        cond = conditionals[0]
        assert "DRAFT" in cond.branches
        assert "IMPROVE" in cond.branches
        assert "DEBUG" in cond.branches


def test_transitions_between_stages():
    wf = build_ai_sci_v2_workflow()
    transitions = [c for c in wf.root.children if isinstance(c, FnNode) and "transition" in c.name]
    assert len(transitions) == 3


def test_knobs():
    knobs = build_ai_sci_v2_knobs()
    names = {k.name for k in knobs}
    assert "temperature" in names
    assert "stage_budget" in names
    assert "debug_prob" in names
    for k in knobs:
        assert k.default in k.bounds


def test_memory_declarations():
    mem = build_ai_sci_v2_memory()
    assert len(mem) >= 1


def test_fn_nodes_resolve():
    wf = build_ai_sci_v2_workflow()
    fn_nodes = collect_nodes(wf.root, FnNode)
    for fn in fn_nodes:
        module_path, func_name = fn.callable_name.split(":")
        module = importlib.import_module(module_path)
        assert hasattr(module, func_name), f"{fn.callable_name} not importable"


def test_registry_discovers():
    from srf.registry import ModeRegistry
    registry = ModeRegistry()
    assert "ai_sci_v2" in registry.list_modes()


