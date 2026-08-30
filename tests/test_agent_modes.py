"""Tests for agent modes: AutoResearch (#13), Karpathy (#14), AutoScientists (#15), AI-Sci V1 (#20)."""

import importlib

from srf._factory_shim import AgentNode, FnNode, LLMNode, Loop, Package, Parallel, Sequential
from tests.conftest import collect_nodes


class TestAutoResearch:
    def test_workflow_structure(self):
        from srf.modes.autoresearch import build_autoresearch_workflow
        wf = build_autoresearch_workflow()
        assert wf.name == "autoresearch"
        assert isinstance(wf.root, Sequential)
        # research, research_llm, optimization loop
        assert len(wf.root.children) == 3
        assert isinstance(wf.root.children[2], Loop)

    def test_knobs(self):
        from srf.modes.autoresearch import build_autoresearch_knobs
        knobs = build_autoresearch_knobs()
        for k in knobs:
            assert k.default in k.bounds

    def test_fn_nodes_resolve(self):
        from srf.modes.autoresearch import build_autoresearch_workflow
        wf = build_autoresearch_workflow()
        for fn in collect_nodes(wf.root, FnNode):
            module_path, func_name = fn.callable_name.split(":")
            module = importlib.import_module(module_path)
            assert hasattr(module, func_name)

    def test_registry_discovers(self):
        from srf.registry import ModeRegistry
        assert "autoresearch" in ModeRegistry().list_modes()


class TestKarpathy:
    def test_workflow_structure(self):
        from srf.modes.karpathy import build_karpathy_workflow
        wf = build_karpathy_workflow()
        assert wf.name == "karpathy"
        assert isinstance(wf.root, Loop)
        body = wf.root.body
        assert isinstance(body, Sequential)

    def test_has_agent_node(self):
        from srf.modes.karpathy import build_karpathy_workflow
        wf = build_karpathy_workflow()
        agents = collect_nodes(wf.root, AgentNode)
        assert len(agents) == 1
        assert agents[0].model == "sonnet"
        assert agents[0].max_turns == 10

    def test_knobs(self):
        from srf.modes.karpathy import build_karpathy_knobs
        knobs = build_karpathy_knobs()
        names = {k.name for k in knobs}
        assert "max_turns" in names
        for k in knobs:
            assert k.default in k.bounds

    def test_fn_nodes_resolve(self):
        from srf.modes.karpathy import build_karpathy_workflow
        wf = build_karpathy_workflow()
        for fn in collect_nodes(wf.root, FnNode):
            module_path, func_name = fn.callable_name.split(":")
            module = importlib.import_module(module_path)
            assert hasattr(module, func_name)

    def test_registry_discovers(self):
        from srf.registry import ModeRegistry
        assert "karpathy" in ModeRegistry().list_modes()


class TestAutoScientists:
    def test_workflow_structure(self):
        from srf.modes.autoscientists import build_autoscientists_workflow
        wf = build_autoscientists_workflow()
        assert wf.name == "autoscientists"
        assert isinstance(wf.root, Sequential)
        # parallel, merge_prompt, merge_gen, eval, update
        assert isinstance(wf.root.children[0], Parallel)

    def test_parallel_scientists(self):
        from srf.modes.autoscientists import build_autoscientists_workflow
        wf = build_autoscientists_workflow()
        parallel = wf.root.children[0]
        assert isinstance(parallel, Parallel)
        assert len(parallel.children) == 3
        for child in parallel.children:
            assert isinstance(child, Package)

    def test_knobs(self):
        from srf.modes.autoscientists import build_autoscientists_knobs
        knobs = build_autoscientists_knobs()
        names = {k.name for k in knobs}
        assert "n_scientists" in names
        for k in knobs:
            assert k.default in k.bounds

    def test_fn_nodes_resolve(self):
        from srf.modes.autoscientists import build_autoscientists_workflow
        wf = build_autoscientists_workflow()
        for fn in collect_nodes(wf.root, FnNode):
            module_path, func_name = fn.callable_name.split(":")
            module = importlib.import_module(module_path)
            assert hasattr(module, func_name)

    def test_registry_discovers(self):
        from srf.registry import ModeRegistry
        assert "autoscientists" in ModeRegistry().list_modes()


class TestAISciV1:
    def test_workflow_structure(self):
        from srf.modes.ai_sci_v1 import build_ai_sci_v1_workflow
        wf = build_ai_sci_v1_workflow()
        assert wf.name == "ai_sci_v1"
        assert isinstance(wf.root, Sequential)
        # ideation, ideation_llm, exp_loop, writeup, writeup_llm, review, review_llm
        assert len(wf.root.children) == 7

    def test_has_experiment_loop(self):
        from srf.modes.ai_sci_v1 import build_ai_sci_v1_workflow
        wf = build_ai_sci_v1_workflow()
        loops = [c for c in wf.root.children if isinstance(c, Loop)]
        assert len(loops) == 1

    def test_four_stages(self):
        from srf.modes.ai_sci_v1 import build_ai_sci_v1_workflow
        wf = build_ai_sci_v1_workflow()
        llm_nodes = collect_nodes(wf.root, LLMNode)
        # ideation_llm, exp_llm (inside loop), writeup_llm, review_llm
        assert len(llm_nodes) == 4

    def test_knobs(self):
        from srf.modes.ai_sci_v1 import build_ai_sci_v1_knobs
        knobs = build_ai_sci_v1_knobs()
        for k in knobs:
            assert k.default in k.bounds

    def test_fn_nodes_resolve(self):
        from srf.modes.ai_sci_v1 import build_ai_sci_v1_workflow
        wf = build_ai_sci_v1_workflow()
        for fn in collect_nodes(wf.root, FnNode):
            module_path, func_name = fn.callable_name.split(":")
            module = importlib.import_module(module_path)
            assert hasattr(module, func_name)

    def test_registry_discovers(self):
        from srf.registry import ModeRegistry
        assert "ai_sci_v1" in ModeRegistry().list_modes()


class TestAgentNode:
    def test_agent_node_dataclass(self):
        node = AgentNode(name="test", model="sonnet", system_prompt="test",
                         max_turns=5, reads={"input.md"}, writes={"output.py"})
        assert node.name == "test"
        assert node.max_turns == 5


