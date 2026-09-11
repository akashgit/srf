"""Phase 1 gate: every mode is a flat DAG that survives the graph.json boundary.

These are structural tests — they need no LLM and no runtime. The end-to-end
walk through the real DSH spine lives in ``test_spine_load.py``.
"""

from __future__ import annotations

import json

import pytest
from factory.workflow.primitives import FnNode, GateNode, Workflow
from factory.workflow.validation import validate_workflow

from srf.graphs import MODES, all_workflows, graph_dict, load_graph, write_graphs

EXECUTABLE_TYPES = {
    "AgentNode",
    "LLMNode",
    "FnNode",
    "Study",
    "GateNode",
    "ForkNode",
    "JoinNode",
}


@pytest.fixture(scope="module")
def workflows() -> dict[str, Workflow]:
    built = all_workflows()
    assert set(built) == set(MODES), f"registry and MODES disagree: {sorted(set(built) ^ set(MODES))}"
    return built


@pytest.mark.parametrize("mode", MODES)
def test_mode_builds(workflows: dict[str, Workflow], mode: str) -> None:
    workflow = workflows[mode]
    assert workflow.name == mode
    assert workflow.nodes
    assert workflow.start_node in workflow.nodes


@pytest.mark.parametrize("mode", MODES)
def test_mode_is_valid(workflows: dict[str, Workflow], mode: str) -> None:
    assert validate_workflow(workflows[mode]) == []


@pytest.mark.parametrize("mode", MODES)
def test_graph_json_round_trips(workflows: dict[str, Workflow], mode: str) -> None:
    """``to_dict()`` → ``from_dict()`` must be lossless, both directions."""
    original = workflows[mode]
    reloaded = Workflow.from_dict(original.to_dict())
    assert reloaded.to_dict() == original.to_dict()
    assert reloaded.name == original.name
    assert reloaded.start_node == original.start_node


@pytest.mark.parametrize("mode", MODES)
def test_graph_is_flat_not_nested(workflows: dict[str, Workflow], mode: str) -> None:
    """The IR is a node table plus an edge list — never a tree of containers."""
    payload = graph_dict(mode)
    assert set(payload) <= {
        "name",
        "nodes",
        "edges",
        "start_node",
        "terminal",
        "task",
        "knob_values",
        "knob_bounds",
        "knob_expandable",
        "knob_specs",
        "declared_capabilities",
    }
    assert isinstance(payload["nodes"], dict)
    assert isinstance(payload["edges"], list)
    for node in payload["nodes"].values():
        assert node["_type"] in EXECUTABLE_TYPES, f"{mode}: {node['_type']} is not executable"
        assert "children" not in node
        assert "body" not in node
        assert "branches" not in node


@pytest.mark.parametrize("mode", MODES)
def test_successors_are_unambiguous(workflows: dict[str, Workflow], mode: str) -> None:
    """The spine's cursor picks the single unconditional edge, so there must be at most one."""
    workflow = workflows[mode]
    for node_id in workflow.nodes:
        unconditional = [
            edge for edge in workflow.edges
            if edge.source == node_id and edge.condition is None
        ]
        assert len(unconditional) <= 1, f"{mode}:{node_id} has {len(unconditional)} unconditional edges"


@pytest.mark.parametrize("mode", MODES)
def test_gates_route_somewhere(workflows: dict[str, Workflow], mode: str) -> None:
    """A gate that routes nowhere would stall the walk."""
    workflow = workflows[mode]
    for node in workflow.nodes.values():
        if not isinstance(node, GateNode):
            continue
        outgoing = [edge for edge in workflow.edges if edge.source == node.id]
        assert outgoing, f"{mode}:{node.id} has no outgoing edge"
        assert node.evaluator_command, f"{mode}:{node.id} has no evaluator command"
        assert node.evaluator_type == "fn", f"{mode}:{node.id} must be a deterministic gate"


@pytest.mark.parametrize("mode", MODES)
def test_cycles_are_gate_reloops(workflows: dict[str, Workflow], mode: str) -> None:
    """Every back edge leaves a gate and carries the ``reloop`` condition."""
    workflow = workflows[mode]
    loops = [
        (edge.source, edge.target)
        for edge in workflow.edges
        if edge.condition is not None and str(edge.condition) == "reloop"
    ]
    for source, _target in loops:
        assert isinstance(workflow.nodes[source], GateNode), f"{mode}: reloop from non-gate {source}"
    assert len(loops) == len(set(loops)), f"{mode}: duplicate reloop edges"


@pytest.mark.parametrize("mode", MODES)
def test_entry_nodes_materialize_the_run(workflows: dict[str, Workflow], mode: str) -> None:
    """Every graph starts by writing the problem, and settings the runtime needs."""
    workflow = workflows[mode]
    start = workflow.nodes[workflow.start_node]
    assert start.id == "task_input"
    assert isinstance(start, FnNode)
    assert {"task.yaml", "eval.py", "initial.py"} <= start.writes


@pytest.mark.parametrize("mode", MODES)
def test_knobs_are_bound_to_real_nodes(workflows: dict[str, Workflow], mode: str) -> None:
    """An ``OptKnob`` names the node it configures; a stale node id is dead config."""
    workflow = workflows[mode]
    for bound_name, bounds in workflow.knob_bounds.items():
        assert bound_name in workflow.knob_values, f"{mode}: bounds without a value for {bound_name}"
        assert bounds, f"{mode}: knob {bound_name} declares empty bounds"


@pytest.mark.parametrize("mode", MODES)
def test_declared_knob_nodes_exist(workflows: dict[str, Workflow], mode: str) -> None:
    from srf.registry import get_mode_registry

    module = get_mode_registry().modules[mode]
    builder = getattr(module, f"build_{mode}_knobs", None)
    if builder is None:
        pytest.skip(f"{mode} declares no knob builder")
    node_ids = set(workflows[mode].nodes)
    for knob in builder():
        assert knob.node_id in node_ids, f"{mode}: knob {knob.name} points at missing node {knob.node_id}"
        assert knob.default in knob.bounds, f"{mode}: knob {knob.name} default is outside its bounds"


@pytest.mark.parametrize("mode", MODES)
def test_op_callables_resolve(workflows: dict[str, Workflow], mode: str) -> None:
    """A declared ``module:function`` must exist, so the runtime can call it."""
    import importlib

    for node in workflows[mode].nodes.values():
        callable_name = getattr(node, "callable_name", None)
        if not callable_name:
            continue
        module_path, _, function = callable_name.partition(":")
        module = importlib.import_module(module_path)
        assert hasattr(module, function), f"{mode}:{node.id} → {callable_name} is missing"


@pytest.mark.parametrize("mode", MODES)
def test_llm_and_agent_nodes_carry_a_prompt(workflows: dict[str, Workflow], mode: str) -> None:
    for node in workflows[mode].nodes.values():
        type_name = type(node).__name__
        if type_name == "LLMNode":
            assert node.system_prompt, f"{mode}:{node.id} has no system prompt"
        if type_name == "AgentNode":
            assert node.prompt_template, f"{mode}:{node.id} has no prompt template"


def test_write_graphs_emits_one_file_per_mode(tmp_path) -> None:
    written = write_graphs(tmp_path)
    assert [path.name for path in written] == [f"{mode}.graph.json" for mode in MODES]
    for path in written:
        payload = json.loads(path.read_text())
        assert payload["name"] in MODES
        reloaded = load_graph(path)
        assert reloaded.to_dict() == payload


def test_graph_dict_rejects_unknown_mode() -> None:
    with pytest.raises(KeyError):
        graph_dict("not_a_mode")


@pytest.mark.parametrize("mode", MODES)
def test_every_node_is_reachable(workflows: dict[str, Workflow], mode: str) -> None:
    """A node the walk cannot reach is dead weight in the graph."""
    workflow = workflows[mode]
    reachable = {workflow.start_node}
    frontier = [workflow.start_node]
    while frontier:
        current = frontier.pop()
        node = workflow.nodes[current]
        targets = [edge.target for edge in workflow.edges if edge.source == current]
        targets += list(getattr(node, "targets", []) or [])
        for target in targets:
            if target in workflow.nodes and target not in reachable:
                reachable.add(target)
                frontier.append(target)
    assert reachable == set(workflow.nodes), f"{mode}: unreachable {sorted(set(workflow.nodes) - reachable)}"


def test_edges_reference_real_nodes(workflows: dict[str, Workflow]) -> None:
    for mode, workflow in workflows.items():
        for edge in workflow.edges:
            assert edge.source in workflow.nodes, f"{mode}: dangling source {edge.source}"
            assert edge.target in workflow.nodes, f"{mode}: dangling target {edge.target}"


def test_node_id_matches_table_key(workflows: dict[str, Workflow]) -> None:
    for mode, workflow in workflows.items():
        for key, node in workflow.nodes.items():
            assert node.id == key, f"{mode}: node keyed {key} declares id {node.id}"


@pytest.mark.parametrize("mode", MODES)
def test_llm_and_agent_nodes_are_model_and_provider_agnostic(workflows: dict[str, Workflow], mode: str) -> None:
    """A graph names neither a model nor a provider: the runtime picks both."""
    for node in workflows[mode].nodes.values():
        type_name = type(node).__name__
        if type_name == "LLMNode":
            assert node.model == "", f"{mode}:{node.id} pins model {node.model!r}"
            assert node.provider == "auto", f"{mode}:{node.id} pins provider {node.provider!r}"
        if type_name == "AgentNode":
            assert node.model == "", f"{mode}:{node.id} pins model {node.model!r}"
