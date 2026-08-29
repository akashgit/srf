"""Tests for task discovery and schema validation."""

from pathlib import Path

from srf.tasks.registry import TaskRegistry, _parse_yaml


def test_task_discovery():
    registry = TaskRegistry()
    names = registry.names()
    assert "circle_packing" in names
    assert "autocorrelation_inequality" in names
    assert "trimul" in names


def test_task_has_required_fields():
    registry = TaskRegistry()
    for name in registry.names():
        task = registry.get(name)
        assert task is not None, f"Task {name} not found"
        assert "name" in task
        assert "category" in task
        assert "description" in task
        assert "eval_command" in task


def test_list_by_category():
    registry = TaskRegistry()
    math_tasks = registry.list_by_category("math")
    assert len(math_tasks) >= 2
    for t in math_tasks:
        assert t["category"] == "math"


def test_parse_yaml_basic():
    text = """
name: test
category: math
description: "A test task"
maximize: true
timeout: 30
"""
    result = _parse_yaml(text)
    assert result["name"] == "test"
    assert result["category"] == "math"
    assert result["maximize"] is True
    assert result["timeout"] == 30


def test_parse_yaml_multiline():
    text = """
name: test
initial_code: |
  def solve():
      return 42
metric: score
"""
    result = _parse_yaml(text)
    assert result["name"] == "test"
    assert "def solve" in result["initial_code"]
    assert result["metric"] == "score"


def test_task_dirs_have_eval_and_initial():
    registry = TaskRegistry()
    for name in registry.names():
        task = registry.get(name)
        task_dir = Path(task["_dir"])
        assert (task_dir / "eval.py").exists(), f"{name} missing eval.py"
        assert (task_dir / "initial.py").exists(), f"{name} missing initial.py"
