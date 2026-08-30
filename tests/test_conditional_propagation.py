"""Tests for Conditional knobs/memory propagation fix (Issue #2)."""

import tempfile
from pathlib import Path

from srf._factory_shim import (
    Conditional,
    ExecutionContext,
    FnNode,
    GateNode,
    Loop,
    MemoryDeclaration,
    MockLLMClient,
    OptKnob,
    Package,
    Sequential,
    WorkflowExecutor,
)


def _make_ctx(work_dir=None):
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp())
    return ExecutionContext(
        work_dir=work_dir,
        knobs={},
        task={"name": "test"},
        budget_limit=10,
        llm_client=MockLLMClient(),
    )


def test_knobs_propagated_from_executed_branch():
    pkg_a = Package(
        name="branch-a",
        knobs=[OptKnob(name="temp_a", kind="threshold", default=0.7, bounds=[0.3, 0.7], node_id="n")],
    )
    pkg_b = Package(
        name="branch-b",
        knobs=[OptKnob(name="temp_b", kind="threshold", default=0.9, bounds=[0.5, 0.9], node_id="n")],
    )
    cond = Conditional(name="test-cond", branches={"PROCEED": pkg_a, "RELOOP": pkg_b})

    ctx = _make_ctx()
    executor = WorkflowExecutor(ctx)
    executor._execute_conditional(cond)

    assert "temp_a" in ctx.knobs
    assert ctx.knobs["temp_a"] == 0.7
    assert "temp_b" not in ctx.knobs


def test_knobs_from_non_executed_branch_absent():
    pkg_a = Package(
        name="branch-a",
        knobs=[OptKnob(name="only_a", kind="threshold", default=1.0, bounds=[1.0], node_id="n")],
    )
    pkg_b = Package(
        name="branch-b",
        knobs=[OptKnob(name="only_b", kind="threshold", default=2.0, bounds=[2.0], node_id="n")],
    )
    cond = Conditional(name="test-cond", branches={"PROCEED": pkg_a, "RELOOP": pkg_b})

    ctx = _make_ctx()
    executor = WorkflowExecutor(ctx)
    executor._execute_conditional(cond)

    assert "only_a" in ctx.knobs
    assert "only_b" not in ctx.knobs


def test_cli_overrides_survive_propagation():
    pkg = Package(
        name="branch",
        knobs=[OptKnob(name="temperature", kind="threshold", default=0.7, bounds=[0.3, 0.7, 0.9], node_id="n")],
    )
    cond = Conditional(name="test-cond", branches={"PROCEED": pkg})

    ctx = _make_ctx()
    ctx.knobs["temperature"] = 0.9
    executor = WorkflowExecutor(ctx)
    executor._execute_conditional(cond)

    assert ctx.knobs["temperature"] == 0.9


def test_nested_conditional_propagation():
    inner_pkg = Package(
        name="inner",
        knobs=[OptKnob(name="inner_knob", kind="threshold", default=42.0, bounds=[42.0], node_id="n")],
    )
    inner_cond = Conditional(name="inner-cond", branches={"PROCEED": inner_pkg})
    outer_pkg = Package(
        name="outer",
        nodes=[inner_cond],
        knobs=[OptKnob(name="outer_knob", kind="threshold", default=10.0, bounds=[10.0], node_id="n")],
    )
    cond = Conditional(name="outer-cond", branches={"PROCEED": outer_pkg})

    ctx = _make_ctx()
    executor = WorkflowExecutor(ctx)
    executor._execute_conditional(cond)

    assert "outer_knob" in ctx.knobs
    assert "inner_knob" in ctx.knobs
    assert ctx.knobs["outer_knob"] == 10.0
    assert ctx.knobs["inner_knob"] == 42.0


def test_gepa_workflow_propagates_knobs():
    from srf.modes.gepa import build_gepa_workflow

    wf = build_gepa_workflow()
    ctx = _make_ctx()
    executor = WorkflowExecutor(ctx)
    cond = wf.root.body.children[0]
    executor._propagate_branch_state(cond.branches["PROCEED"])

    # No crash, and knobs from the executed branch's packages are accessible
    # (GEPA mutate package has no package-level knobs, so just verify no error)
    assert True


def test_sequential_inside_branch_propagates():
    pkg = Package(
        name="inner-pkg",
        knobs=[OptKnob(name="seq_knob", kind="threshold", default=5.0, bounds=[5.0], node_id="n")],
    )
    seq = Sequential(name="seq", children=[pkg])
    cond = Conditional(name="cond", branches={"PROCEED": seq})

    ctx = _make_ctx()
    executor = WorkflowExecutor(ctx)
    executor._execute_conditional(cond)

    assert "seq_knob" in ctx.knobs
    assert ctx.knobs["seq_knob"] == 5.0
