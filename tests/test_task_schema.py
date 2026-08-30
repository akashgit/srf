"""Tests for task definition schema (Issue #1)."""

import pytest
from pydantic import ValidationError

from srf.tasks.schema import TaskDefinition


def _valid_task_data():
    return {
        "name": "test_task",
        "category": "math",
        "description": "A test task",
        "initial_code": "def solve(): return 0",
        "eval_command": "python eval.py",
        "metric": "score",
        "maximize": True,
    }


def test_valid_task_passes():
    td = TaskDefinition(**_valid_task_data())
    assert td.name == "test_task"
    assert td.category == "math"
    assert td.maximize is True


def test_missing_name_raises():
    data = _valid_task_data()
    del data["name"]
    with pytest.raises(ValidationError):
        TaskDefinition(**data)


def test_missing_category_raises():
    data = _valid_task_data()
    del data["category"]
    with pytest.raises(ValidationError):
        TaskDefinition(**data)


def test_missing_description_raises():
    data = _valid_task_data()
    del data["description"]
    with pytest.raises(ValidationError):
        TaskDefinition(**data)


def test_missing_initial_code_raises():
    data = _valid_task_data()
    del data["initial_code"]
    with pytest.raises(ValidationError):
        TaskDefinition(**data)


def test_invalid_type_raises():
    data = _valid_task_data()
    data["maximize"] = "not_a_bool"
    with pytest.raises(ValidationError):
        TaskDefinition(**data)


def test_extra_fields_accepted():
    data = _valid_task_data()
    data["custom_field"] = "extra"
    td = TaskDefinition(**data)
    assert td.name == "test_task"


def test_defaults():
    data = _valid_task_data()
    td = TaskDefinition(**data)
    assert td.eval_command == "python eval.py"
    assert td.metric == "score"
    assert td.timeout == 30


def test_optional_fields():
    data = _valid_task_data()
    data["reference_score"] = 2.634
    data["allowed_imports"] = ["numpy", "scipy"]
    td = TaskDefinition(**data)
    assert td.reference_score == 2.634
    assert td.allowed_imports == ["numpy", "scipy"]


def test_existing_tasks_validate():
    from srf.tasks.registry import TaskRegistry

    registry = TaskRegistry()
    for name in registry.names():
        td = registry.get_validated(name)
        assert td is not None, f"Task {name} failed validation"
        assert td.name == name


def test_get_returns_validated_dict():
    from srf.tasks.registry import TaskRegistry

    registry = TaskRegistry()
    result = registry.get("circle_packing")
    assert result is not None
    assert result["name"] == "circle_packing"
    assert result["category"] == "math"
    assert result["maximize"] is True


def test_get_raw_returns_raw_dict():
    from srf.tasks.registry import TaskRegistry

    registry = TaskRegistry()
    raw = registry.get_raw("circle_packing")
    assert raw is not None
    assert "_dir" in raw
