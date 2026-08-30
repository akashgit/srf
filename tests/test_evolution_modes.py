"""Tests for evolution modes: OpenEvolve (#9), ShinkaEvolve (#19), AdaEvolve (#16), EvoX (#17)."""

import importlib

from srf._factory_shim import Conditional, FnNode, GateNode, LLMNode, Loop, Package, Sequential
from srf.ops.common.migration import ring_migrate, should_migrate
from srf.ops.common.reflection import analyze_stagnation, build_reflection_prompt
from tests.conftest import collect_nodes


class TestOpenEvolve:
    def test_workflow_structure(self):
        from srf.modes.openevolve import build_openevolve_workflow
        wf = build_openevolve_workflow()
        assert wf.name == "openevolve"
        assert isinstance(wf.root, Loop)
        assert isinstance(wf.root.body, Sequential)
        assert len(wf.root.body.children) == 5

    def test_knobs(self):
        from srf.modes.openevolve import build_openevolve_knobs
        knobs = build_openevolve_knobs()
        names = {k.name for k in knobs}
        assert "n_islands" in names
        assert "migration_interval" in names
        for k in knobs:
            assert k.default in k.bounds

    def test_fn_nodes_resolve(self):
        from srf.modes.openevolve import build_openevolve_workflow
        wf = build_openevolve_workflow()
        for child in wf.root.body.children:
            if isinstance(child, FnNode):
                module_path, func_name = child.callable_name.split(":")
                module = importlib.import_module(module_path)
                assert hasattr(module, func_name)

    def test_registry_discovers(self):
        from srf.registry import ModeRegistry
        registry = ModeRegistry()
        assert "openevolve" in registry.list_modes()


class TestShinkaEvolve:
    def test_workflow_structure(self):
        from srf.modes.shinka import build_shinka_workflow
        wf = build_shinka_workflow()
        assert wf.name == "shinka"
        assert isinstance(wf.root, Loop)
        assert isinstance(wf.root.body, Sequential)

    def test_knobs(self):
        from srf.modes.shinka import build_shinka_knobs
        knobs = build_shinka_knobs()
        names = {k.name for k in knobs}
        assert "reflect_interval" in names
        for k in knobs:
            assert k.default in k.bounds

    def test_fn_nodes_resolve(self):
        from srf.modes.shinka import build_shinka_workflow
        wf = build_shinka_workflow()
        for child in wf.root.body.children:
            if isinstance(child, FnNode):
                module_path, func_name = child.callable_name.split(":")
                module = importlib.import_module(module_path)
                assert hasattr(module, func_name)

    def test_registry_discovers(self):
        from srf.registry import ModeRegistry
        registry = ModeRegistry()
        assert "shinka" in registry.list_modes()


class TestAdaEvolve:
    def test_workflow_structure(self):
        from srf.modes.adaevolve import build_adaevolve_workflow
        wf = build_adaevolve_workflow()
        assert wf.name == "adaevolve"
        assert isinstance(wf.root, Loop)
        body = wf.root.body
        assert isinstance(body, Sequential)

    def test_has_conditional_meta_strategy(self):
        from srf.modes.adaevolve import build_adaevolve_workflow
        wf = build_adaevolve_workflow()
        conditionals = [c for c in wf.root.body.children if isinstance(c, Conditional)]
        assert len(conditionals) >= 1
        cond = conditionals[0]
        assert "NORMAL" in cond.branches
        assert "META" in cond.branches

    def test_knobs(self):
        from srf.modes.adaevolve import build_adaevolve_knobs
        knobs = build_adaevolve_knobs()
        names = {k.name for k in knobs}
        assert "meta_temperature" in names
        for k in knobs:
            assert k.default in k.bounds

    def test_fn_nodes_resolve(self):
        from srf.modes.adaevolve import build_adaevolve_workflow
        wf = build_adaevolve_workflow()
        fn_nodes = collect_nodes(wf.root, FnNode)
        for fn in fn_nodes:
            module_path, func_name = fn.callable_name.split(":")
            module = importlib.import_module(module_path)
            assert hasattr(module, func_name)

    def test_registry_discovers(self):
        from srf.registry import ModeRegistry
        registry = ModeRegistry()
        assert "adaevolve" in registry.list_modes()


class TestEvoX:
    def test_workflow_structure(self):
        from srf.modes.evox import build_evox_workflow
        wf = build_evox_workflow()
        assert wf.name == "evox"
        assert isinstance(wf.root, Loop)

    def test_knobs(self):
        from srf.modes.evox import build_evox_knobs
        knobs = build_evox_knobs()
        names = {k.name for k in knobs}
        assert "meta_interval" in names
        for k in knobs:
            assert k.default in k.bounds

    def test_fn_nodes_resolve(self):
        from srf.modes.evox import build_evox_workflow
        wf = build_evox_workflow()
        for child in wf.root.body.children:
            if isinstance(child, FnNode):
                module_path, func_name = child.callable_name.split(":")
                module = importlib.import_module(module_path)
                assert hasattr(module, func_name)

    def test_registry_discovers(self):
        from srf.registry import ModeRegistry
        registry = ModeRegistry()
        assert "evox" in registry.list_modes()


class TestMigration:
    def test_ring_migrate(self):
        islands = [
            [{"id": "a", "score": 0.5}],
            [{"id": "b", "score": 0.8}],
            [{"id": "c", "score": 0.3}],
        ]
        result = ring_migrate(islands)
        assert len(result) == 3
        # Island 1 should have received island 0's best
        assert any(p["id"] == "a" for p in result[1])

    def test_should_migrate(self):
        assert should_migrate(0, 10) is False
        assert should_migrate(10, 10) is True
        assert should_migrate(15, 10) is False
        assert should_migrate(20, 10) is True


class TestReflection:
    def test_analyze_stagnation_not_stagnating(self):
        history = [{"score": i * 0.1, "improved": True} for i in range(10)]
        result = analyze_stagnation(history)
        assert result["stagnating"] is False

    def test_analyze_stagnation_yes(self):
        history = [{"score": 0.5, "improved": False} for _ in range(10)]
        result = analyze_stagnation(history)
        assert result["stagnating"] is True

    def test_build_reflection_prompt(self):
        task = {"name": "test", "category": "math", "description": "test task"}
        history = [{"score": 0.5, "action": "mutate", "improved": True}]
        prompt = build_reflection_prompt(task, history)
        assert "test" in prompt
        assert "mutate" in prompt

    def test_insufficient_history(self):
        result = analyze_stagnation([{"score": 0.5}])
        assert result["stagnating"] is False
        assert result["reason"] == "insufficient_history"


