"""Tests for GEPA mode — graph validation, compile round-trip, OptKnob mutation."""

import importlib

from srf._factory_shim import (
    Conditional,
    FnNode,
    GateNode,
    LLMNode,
    Loop,
    Package,
    Sequential,
)
from tests.conftest import collect_nodes
from srf.modes.gepa import (
    build_gepa_knobs,
    build_gepa_memory,
    build_gepa_workflow,
)


def test_workflow_structure():
    wf = build_gepa_workflow()
    assert wf.name == "gepa"
    assert isinstance(wf.root, Loop)
    assert wf.root.name == "gepa"
    assert wf.root.max_iterations == 500

    body = wf.root.body
    assert isinstance(body, Sequential)
    assert body.name == "gepa-iteration"
    assert len(body.children) == 2

    action = body.children[0]
    assert isinstance(action, Conditional)
    assert action.name == "gepa-action"

    eval_pkg = body.children[1]
    assert isinstance(eval_pkg, Package)
    assert eval_pkg.name == "gepa-eval"

    assert isinstance(wf.root.gate, GateNode)
    assert "budget" in wf.root.gate.evaluator_command


def test_conditional_branches():
    wf = build_gepa_workflow()
    action = wf.root.body.children[0]
    assert "PROCEED" in action.branches
    assert "RELOOP" in action.branches

    mutate = action.branches["PROCEED"]
    merge = action.branches["RELOOP"]
    assert isinstance(mutate, Package)
    assert mutate.name == "gepa-mutate"
    assert isinstance(merge, Package)
    assert merge.name == "gepa-merge"


def test_fn_node_callables_resolve():
    wf = build_gepa_workflow()
    fn_nodes = collect_nodes(wf.root, FnNode)
    for fn in fn_nodes:
        module_path, func_name = fn.callable_name.split(":")
        module = importlib.import_module(module_path)
        assert hasattr(module, func_name), f"{fn.callable_name} not importable"


def test_llm_nodes_have_system_prompts():
    wf = build_gepa_workflow()
    llm_nodes = collect_nodes(wf.root, LLMNode)
    assert len(llm_nodes) == 2
    for llm in llm_nodes:
        assert llm.system_prompt, f"LLMNode {llm.name} missing system_prompt"
        assert llm.model == "sonnet"


def test_opt_knobs():
    knobs = build_gepa_knobs()
    assert len(knobs) == 5
    names = {k.name for k in knobs}
    assert names == {
        "temperature", "parent_selection", "max_rejection_context",
        "merge_stagnation_threshold", "acceptance_mode",
    }
    for knob in knobs:
        assert knob.default in knob.bounds, f"Knob {knob.name}: default not in bounds"
        assert len(knob.bounds) > 0


def test_memory_declarations():
    mem = build_gepa_memory()
    assert len(mem) == 3
    namespaces = {m.namespace for m in mem}
    assert namespaces == {"gepa.population", "gepa.genealogy", "gepa.rejections"}


def test_state_contracts():
    wf = build_gepa_workflow()
    mutate = wf.root.body.children[0].branches["PROCEED"]
    merge = wf.root.body.children[0].branches["RELOOP"]
    eval_pkg = wf.root.body.children[1]

    assert "population.json" in mutate.state_contract.requires
    assert "task.yaml" in mutate.state_contract.requires
    assert "candidate.py" in mutate.state_contract.produces

    assert "population.json" in merge.state_contract.requires
    assert "genealogy.json" in merge.state_contract.requires
    assert "candidate.py" in merge.state_contract.produces

    assert "candidate.py" in eval_pkg.state_contract.requires
    assert "eval_result.json" in eval_pkg.state_contract.produces


def test_gate_nodes():
    wf = build_gepa_workflow()
    merge_gate = wf.root.body.children[0].gate
    budget_gate = wf.root.gate

    assert isinstance(merge_gate, GateNode)
    assert "srf.ops.gepa.decision" in merge_gate.evaluator_command
    assert "should_merge" in merge_gate.evaluator_command

    assert isinstance(budget_gate, GateNode)
    assert "srf.ops.common.budget" in budget_gate.evaluator_command
    assert "check" in budget_gate.evaluator_command


