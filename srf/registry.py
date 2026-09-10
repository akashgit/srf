"""Mode and task registries — auto-discovers modes and tasks."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable

import structlog

from factory.workflow.primitives import Workflow
from srf.tasks.registry import TaskRegistry

logger = structlog.get_logger()


class ModeRegistry:
    """Auto-discovers mode modules in srf/modes/ and maps names to graph builders.

    A module is a mode when it defines ``build_<name>_workflow()``; the module
    itself is kept so callers can also reach its knob and memory declarations.
    A module that fails to import is reported and skipped, never silently
    treated as absent.
    """

    def __init__(self) -> None:
        self.modules: dict[str, Any] = {}
        self._discover()

    def _discover(self) -> None:
        import srf.modes as modes_pkg

        modes_path = Path(modes_pkg.__file__).parent
        for _finder, name, _ispkg in pkgutil.iter_modules([str(modes_path)]):
            try:
                module = importlib.import_module(f"srf.modes.{name}")
            except Exception as error:  # noqa: BLE001 - reported, not swallowed
                logger.warning("mode.load_error", name=name, error=str(error))
                continue
            if hasattr(module, f"build_{name}_workflow"):
                self.modules[name] = module
                logger.debug("mode.discovered", name=name)

    def builder(self, name: str) -> Callable[[], Workflow] | None:
        module = self.modules.get(name)
        return getattr(module, f"build_{name}_workflow", None) if module else None

    def get(self, name: str) -> Workflow | None:
        builder = self.builder(name)
        return builder() if builder else None

    def list_modes(self) -> list[str]:
        return list(self.modules)


_mode_registry: ModeRegistry | None = None
_task_registry: TaskRegistry | None = None


def get_mode_registry() -> ModeRegistry:
    global _mode_registry
    if _mode_registry is None:
        _mode_registry = ModeRegistry()
    return _mode_registry


def get_task_registry() -> TaskRegistry:
    global _task_registry
    if _task_registry is None:
        _task_registry = TaskRegistry()
    return _task_registry
