"""Task registry — discovers tasks by directory convention under srf/tasks/."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

try:
    import yaml
except ImportError:
    yaml = None


def _parse_yaml(text: str) -> dict[str, Any]:
    """Parse YAML without requiring PyYAML — handles the simple task.yaml format."""
    if yaml:
        return yaml.safe_load(text)
    result: dict[str, Any] = {}
    current_key = None
    multiline_value: list[str] = []
    in_multiline = False

    for line in text.splitlines():
        if in_multiline:
            if line and not line[0].isspace() and not line.startswith("  "):
                result[current_key] = "\n".join(multiline_value).strip()
                in_multiline = False
            else:
                multiline_value.append(line.lstrip())
                continue

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "|":
                current_key = key
                multiline_value = []
                in_multiline = True
            elif value.startswith('"') and value.endswith('"'):
                result[key] = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                result[key] = value[1:-1]
            elif value.lower() == "true":
                result[key] = True
            elif value.lower() == "false":
                result[key] = False
            elif value:
                try:
                    result[key] = float(value) if "." in value else int(value)
                except ValueError:
                    result[key] = value
            else:
                result[key] = ""

    if in_multiline and current_key:
        result[current_key] = "\n".join(multiline_value).strip()

    return result


class TaskRegistry:
    def __init__(self, tasks_root: Path | None = None):
        self._tasks_root = tasks_root or Path(__file__).parent
        self._tasks: dict[str, dict[str, Any]] = {}
        self._discover()

    def _discover(self) -> None:
        for task_yaml in self._tasks_root.rglob("task.yaml"):
            task_dir = task_yaml.parent
            category = task_dir.parent.name
            name = task_dir.name
            try:
                config = _parse_yaml(task_yaml.read_text())
                config.setdefault("name", name)
                config.setdefault("category", category)
                config["_dir"] = str(task_dir)
                self._tasks[name] = config
                logger.debug("task.discovered", name=name, category=category)
            except Exception as e:
                logger.warning("task.load_error", name=name, error=str(e))

    def get(self, name: str) -> dict[str, Any] | None:
        return self._tasks.get(name)

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._tasks.values())

    def list_by_category(self, category: str) -> list[dict[str, Any]]:
        return [t for t in self._tasks.values() if t.get("category") == category]

    def names(self) -> list[str]:
        return list(self._tasks.keys())
