"""SRF CLI — inspect the packages and emit the graphs the runtime executes.

SRF is a pure package, so this CLI has no working ``run`` command: the DSH
workflow spine is the only runtime. What it does is list the packages and write
the graph IR (``graph.json``) that the runtime loads.

Usage:
  srf modes
  srf tasks [--category math]
  srf graph --mode gepa [--out graphs/gepa.graph.json]
  srf graphs [--out graphs]
  srf probe [--graphs graphs]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from srf.graphs import (
    GRAPHS_DIR,
    MODES,
    SPINE_PROBE,
    TSX_LOADER,
    graph_dict,
    graph_path,
    write_graphs,
)
from srf.logging.config import configure_logging

RUNTIME_HINT = (
    "SRF declares graphs; the DSH workflow spine executes them. Run a mode with "
    "`dsh science run --mode <mode> --task <task>` (PLAN.md Phase 4), or write the "
    "graph with `srf graph --mode <mode>` and load it into the spine."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="srf", description="Scientific Research Factory")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("modes", help="List registered modes")

    tasks_parser = subparsers.add_parser("tasks", help="List available tasks")
    tasks_parser.add_argument("--category", default=None, help="Filter by category")

    graph_parser = subparsers.add_parser("graph", help="Emit one mode's graph.json")
    graph_parser.add_argument("--mode", required=True, help="Mode name (e.g., gepa)")
    graph_parser.add_argument("--out", default=None, help="Write to this path instead of stdout")

    graphs_parser = subparsers.add_parser("graphs", help="Emit every mode's graph.json")
    graphs_parser.add_argument("--out", default=str(GRAPHS_DIR), help="Output directory")

    probe_parser = subparsers.add_parser("probe", help="Load graphs into the DSH spine")
    probe_parser.add_argument("--graphs", default=str(GRAPHS_DIR), help="Directory of graph.json")
    probe_parser.add_argument(
        "--spine",
        default=None,
        help="file: URL of the spine module (default: the DSH checkout)",
    )

    run_parser = subparsers.add_parser("run", help="(moved to the DSH runtime)")
    run_parser.add_argument("--mode", required=False, help="Mode name")
    run_parser.add_argument("--task", required=False, help="Task name")

    args = parser.parse_args(argv)
    configure_logging()

    if args.command == "modes":
        return _cmd_modes()
    if args.command == "tasks":
        return _cmd_tasks(args)
    if args.command == "graph":
        return _cmd_graph(args)
    if args.command == "graphs":
        return _cmd_graphs(args)
    if args.command == "probe":
        return _cmd_probe(args)
    if args.command == "run":
        print(RUNTIME_HINT, file=sys.stderr)
        return 1

    parser.print_help()
    return 1


def _cmd_modes() -> int:
    from srf.registry import get_mode_registry

    modes = get_mode_registry().list_modes()
    if not modes:
        print("No modes registered.")
        return 0
    print("Registered modes:")
    for mode in modes:
        print(f"  - {mode}")
    return 0


def _cmd_tasks(args: argparse.Namespace) -> int:
    from srf.registry import get_task_registry

    registry = get_task_registry()
    tasks = registry.list_by_category(args.category) if args.category else registry.list_all()
    if not tasks:
        print("No tasks found.")
        return 0
    print("Available tasks:")
    for task in tasks:
        description = str(task.get("description", ""))[:80]
        print(f"  - {task['name']} [{task.get('category', '?')}]: {description}")
    return 0


def _cmd_graph(args: argparse.Namespace) -> int:
    try:
        payload = graph_dict(args.mode)
    except KeyError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(payload, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(rendered)
        print(args.out)
    else:
        sys.stdout.write(rendered)
    return 0


def _cmd_graphs(args: argparse.Namespace) -> int:
    for path in write_graphs(Path(args.out)):
        print(path)
    return 0


def _cmd_probe(args: argparse.Namespace) -> int:
    directory = Path(args.graphs)
    paths = [graph_path(directory, mode) for mode in MODES]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        print(f"Error: run `srf graphs --out {directory}` first; missing {missing}", file=sys.stderr)
        return 1
    command = [
        "node",
        "--import",
        TSX_LOADER.resolve().as_uri(),
        str(SPINE_PROBE),
        *[str(path) for path in paths],
    ]
    environment = None
    if args.spine:
        environment = {**os.environ, "SRF_SPINE_MODULE": args.spine}
    completed = subprocess.run(command, env=environment, capture_output=True, text=True)
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    sys.exit(main())
