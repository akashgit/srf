"""Mode and task registries — auto-discovers modes and tasks."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable

import structlog

from srf._factory_shim import Workflow
from srf.tasks.registry import TaskRegistry

logger = structlog.get_logger()


class ModeRegistry:
    """Auto-discovers mode modules in srf/modes/ and maps names to Package builders."""

    def __init__(self) -> None:
        self._modes: dict[str, Callable[[], Workflow]] = {}
        self._discover()

    def _discover(self) -> None:
        import srf.modes as modes_pkg

        modes_path = Path(modes_pkg.__file__).parent
        for finder, name, ispkg in pkgutil.iter_modules([str(modes_path)]):
            try:
                module = importlib.import_module(f"srf.modes.{name}")
                builder_name = f"build_{name}_workflow"
                if hasattr(module, builder_name):
                    self._modes[name] = getattr(module, builder_name)
                    logger.debug("mode.discovered", name=name)
            except Exception as e:
                logger.warning("mode.load_error", name=name, error=str(e))

    def get(self, name: str) -> Workflow | None:
        builder = self._modes.get(name)
        if builder:
            return builder()
        return None

    def list_modes(self) -> list[str]:
        return list(self._modes.keys())


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
