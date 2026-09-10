"""Graph emission — the boundary between SRF and the runtime.

SRF defines graphs; DSH executes them. The handoff is ``Workflow.to_dict()``:
one ``graph.json`` per mode, which the workflow spine loads verbatim. Nothing in
this module runs a graph.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from factory.workflow.primitives import Workflow

from srf.registry import get_mode_registry

MODES: tuple[str, ...] = (
    "adaevolve",
    "ai_sci_v1",
    "ai_sci_v2",
    "aide",
    "autoresearch",
    "autoscientists",
    "best_of_n",
    "evox",
    "gepa",
    "karpathy",
    "openevolve",
    "scs",
    "shinka",
)
"""SRF's 13 scientific-discovery harnesses, in name order."""

GRAPHS_DIR = Path(__file__).parent.parent / "graphs"
"""Where ``srf graphs`` writes the emitted IR by default."""

SPINE_PROBE = Path(__file__).parent / "tools" / "spine_probe.mjs"
"""The harness that loads emitted graphs into the real DSH workflow spine."""

DSH_ROOT = Path("/Users/akash/dsh/refactory-dsh/deepseek-harness")
"""The DSH checkout the probe resolves the spine module from; ``DSH_ROOT`` overrides."""


def dsh_root() -> Path:
    """The DSH checkout the probe resolves the spine and its TypeScript loader from."""
    return Path(os.environ.get("DSH_ROOT", DSH_ROOT))


def spine_source() -> Path:
    """The spine module the probe loads — the source, not a stale build artifact."""
    return dsh_root() / "packages" / "workflow" / "workflow-spine" / "src" / "spine.ts"


def tsx_loader() -> Path:
    """The TypeScript ESM loader that lets plain ``node`` import the spine's source."""
    return dsh_root() / "node_modules" / "tsx" / "dist" / "esm" / "index.mjs"


def workflow_for(mode: str) -> Workflow | None:
    """Build one mode's flat-DAG workflow, or ``None`` if the mode is unknown."""
    return get_mode_registry().get(mode)


def all_workflows() -> dict[str, Workflow]:
    """Build every registered mode's workflow, keyed by mode name."""
    registry = get_mode_registry()
    built: dict[str, Workflow] = {}
    for mode in sorted(registry.list_modes()):
        workflow = registry.get(mode)
        if workflow is not None:
            built[mode] = workflow
    return built


def graph_dict(mode: str) -> dict[str, Any]:
    """The mode's ``graph.json`` payload — refactory's ``Workflow.to_dict()``."""
    workflow = workflow_for(mode)
    if workflow is None:
        raise KeyError(f"unknown mode '{mode}'; known modes: {', '.join(MODES)}")
    return workflow.to_dict()


def graph_path(directory: Path, mode: str) -> Path:
    """The path a mode's emitted graph takes inside ``directory``."""
    return directory / f"{mode}.graph.json"


def write_graphs(directory: Path = GRAPHS_DIR, modes: tuple[str, ...] = MODES) -> list[Path]:
    """Write one ``<mode>.graph.json`` per mode. Returns the paths written."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for mode in modes:
        path = graph_path(directory, mode)
        path.write_text(json.dumps(graph_dict(mode), indent=2, sort_keys=False) + "\n")
        written.append(path)
    return written


def load_graph(path: Path) -> Workflow:
    """Load an emitted ``graph.json`` back into a workflow."""
    return Workflow.from_dict(json.loads(Path(path).read_text()))


SPINE_SOURCE = spine_source()
"""The resolved spine module path at import time (see :func:`spine_source`)."""

TSX_LOADER = tsx_loader()
"""The resolved TypeScript loader path at import time (see :func:`tsx_loader`)."""
