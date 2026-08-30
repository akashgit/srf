"""Tests for Best-of-N mode (Issue #12)."""

import importlib

from srf._factory_shim import FnNode, LLMNode, Package, Parallel, Sequential
from tests.conftest import collect_nodes
from srf.modes.best_of_n import (
    build_best_of_n_knobs,
    build_best_of_n_memory,
    build_best_of_n_workflow,
)


def test_workflow_structure():
    wf = build_best_of_n_workflow()
    assert wf.name == "best_of_n"
    assert isinstance(wf.root, Sequential)
    assert len(wf.root.children) == 2

    parallel = wf.root.children[0]
    assert isinstance(parallel, Parallel)
    assert len(parallel.children) == 5

    select = wf.root.children[1]
    assert isinstance(select, FnNode)
    assert select.name == "select_best"


def test_parallel_children_are_packages():
    wf = build_best_of_n_workflow()
    parallel = wf.root.children[0]
    for child in parallel.children:
        assert isinstance(child, Package)


def test_knobs():
    knobs = build_best_of_n_knobs()
    names = {k.name for k in knobs}
    assert "n_candidates" in names
    assert "temperature" in names
    for k in knobs:
        assert k.default in k.bounds


def test_memory_declarations():
    mem = build_best_of_n_memory()
    assert len(mem) >= 1
    namespaces = {m.namespace for m in mem}
    assert "best_of_n.candidates" in namespaces


def test_fn_nodes_resolve():
    wf = build_best_of_n_workflow()
    fn_nodes = collect_nodes(wf.root, FnNode)
    for fn in fn_nodes:
        module_path, func_name = fn.callable_name.split(":")
        module = importlib.import_module(module_path)
        assert hasattr(module, func_name), f"{fn.callable_name} not importable"


def test_llm_nodes():
    wf = build_best_of_n_workflow()
    llm_nodes = collect_nodes(wf.root, LLMNode)
    assert len(llm_nodes) == 5
    for llm in llm_nodes:
        assert llm.system_prompt
        assert llm.model == "sonnet"


def test_registry_discovers():
    from srf.registry import ModeRegistry
    registry = ModeRegistry()
    assert "best_of_n" in registry.list_modes()
    wf = registry.get("best_of_n")
    assert wf is not None
    assert wf.name == "best_of_n"


