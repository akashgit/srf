"""Tests for SCS mode (Issue #18)."""

import importlib
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from srf._factory_shim import FnNode, GateNode, LLMNode, Loop, Sequential
from srf.modes.scs import build_scs_knobs, build_scs_memory, build_scs_workflow
from srf.ops.common.population import PopulationState, Program, make_program_id, quality_diversity_accept
from srf.ops.common.selection import select_best, select_epsilon_greedy, select_parent, select_uniform


def test_workflow_structure():
    wf = build_scs_workflow()
    assert wf.name == "scs"
    assert isinstance(wf.root, Loop)
    assert isinstance(wf.root.body, Sequential)
    assert isinstance(wf.root.gate, GateNode)
    assert len(wf.root.body.children) == 5


def test_knobs():
    knobs = build_scs_knobs()
    names = {k.name for k in knobs}
    assert "temperature" in names
    assert "parent_selection" in names
    for k in knobs:
        assert k.default in k.bounds


def test_memory_declarations():
    mem = build_scs_memory()
    assert len(mem) >= 1


def test_fn_nodes_resolve():
    wf = build_scs_workflow()
    for child in wf.root.body.children:
        if isinstance(child, FnNode):
            module_path, func_name = child.callable_name.split(":")
            module = importlib.import_module(module_path)
            assert hasattr(module, func_name), f"{child.callable_name} not importable"


def test_registry_discovers():
    from srf.registry import ModeRegistry
    registry = ModeRegistry()
    assert "scs" in registry.list_modes()


def test_population_state():
    state = PopulationState()
    p1 = Program(id="p1", code="x=1", score=0.5)
    p2 = Program(id="p2", code="x=2", score=0.8)
    state.add(p1)
    is_new_best = state.add(p2)
    assert is_new_best
    assert state.best_score == 0.8
    assert state.best_id == "p2"


def test_population_state_save_load(tmp_path):
    state = PopulationState()
    state.add(Program(id="p1", code="x=1", score=0.5))
    state.save(tmp_path / "pop.json")
    loaded = PopulationState.load(tmp_path / "pop.json")
    assert "p1" in loaded.programs
    assert loaded.programs["p1"].score == 0.5


def test_make_program_id():
    id1 = make_program_id("def solve(): return 1")
    id2 = make_program_id("def solve(): return 2")
    assert id1 != id2
    assert len(id1) == 12


def test_quality_diversity_accept():
    state = PopulationState()
    state.add(Program(id="best", code="x", score=0.5))
    good = Program(id="g", code="y", score=0.55)
    assert quality_diversity_accept(good, state) is True
    bad = Program(id="b", code="z", score=0.1)
    assert quality_diversity_accept(bad, state) is False
    err = Program(id="e", code="w", score=0.9, error="crash")
    assert quality_diversity_accept(err, state) is False


def test_selection_best():
    progs = [{"id": "a", "score": 0.3}, {"id": "b", "score": 0.9}]
    assert select_best(progs)["id"] == "b"


def test_selection_uniform():
    progs = [{"id": "a", "score": 0.3}, {"id": "b", "score": 0.9}]
    result = select_uniform(progs)
    assert result["id"] in ("a", "b")


def test_selection_epsilon_greedy():
    progs = [{"id": "a", "score": 0.3}, {"id": "b", "score": 0.9}]
    result = select_epsilon_greedy(progs, epsilon=0.0)
    assert result["id"] == "b"


def test_select_parent_dispatch():
    progs = [{"id": "a", "score": 0.3}, {"id": "b", "score": 0.9}]
    result = select_parent(progs, strategy="best")
    assert result["id"] == "b"
