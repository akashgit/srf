"""Phase 1 gate: SRF is a pure package — semantics only, no runtime.

Nothing under ``srf/`` may carry an executor, an LLM client, or a private copy of
refactory's primitives. The graph is the whole interface to the runtime, and the
runtime lives in DSH.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRF_PACKAGE = Path(__file__).parent.parent / "srf"
REMOVED_MODULES = ("srf/_factory_shim.py", "srf/agent_executor.py", "srf/lab/director.py")

RUNTIME_MARKERS = (
    "WorkflowExecutor",
    "ExecutionContext",
    "HttpxLLMClient",
    "OpenAILLMClient",
    "VertexAILLMClient",
    "MockLLMClient",
    "LLMResponse",
    "class Loop",
    "class Sequential",
    "class Parallel",
    "class Conditional",
)


def python_files() -> list[Path]:
    return sorted(SRF_PACKAGE.rglob("*.py"))


def test_removed_runtime_modules_are_gone() -> None:
    root = Path(__file__).parent.parent
    for relative in REMOVED_MODULES:
        assert not (root / relative).exists(), f"{relative} still exists"


def test_no_module_references_the_deleted_shim() -> None:
    offenders = [
        str(path.relative_to(SRF_PACKAGE.parent))
        for path in python_files()
        if "_factory_shim" in path.read_text()
    ]
    assert offenders == []


@pytest.mark.parametrize("path", python_files(), ids=lambda path: path.name)
def test_no_runtime_abstractions_in_the_package(path: Path) -> None:
    """A mode declares a graph; it never gains the ability to walk one."""
    source = path.read_text()
    found = [marker for marker in RUNTIME_MARKERS if marker in source]
    assert found == [], f"{path.name} defines or uses {found}"


@pytest.mark.parametrize(
    "path",
    sorted((SRF_PACKAGE / "modes").glob("*.py")),
    ids=lambda path: path.name,
)
def test_modes_import_only_refactory_and_srf(path: Path) -> None:
    """A mode's dependency surface is refactory's vocabulary plus SRF's own helpers."""
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    allowed_prefixes = ("factory.", "srf.", "__future__")
    unexpected = sorted(
        module for module in modules if not module.startswith(allowed_prefixes)
    )
    assert unexpected == []


def test_srf_declares_refactory_as_a_dependency() -> None:
    """SRF imports refactory's primitives, so it must declare them."""
    pyproject = (SRF_PACKAGE.parent / "pyproject.toml").read_text()
    assert "remote-factory" in pyproject or "factory" in pyproject
