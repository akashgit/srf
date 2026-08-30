"""SRF CLI — entry point for running scientific research workflows.

Usage:
  srf run --mode gepa --task circle_packing --budget 50
  srf run --mode gepa --task circle_packing --knob temperature=0.9 --knob parent_selection=pareto
  srf modes
  srf tasks [--category math]
  srf validate --mode gepa --task circle_packing --baseline-trace <path>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

import structlog

from srf.logging.config import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="srf", description="Scientific Research Factory")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run a mode on a task")
    run_parser.add_argument("--mode", required=True, help="Mode name (e.g., gepa)")
    run_parser.add_argument("--task", required=True, help="Task name (e.g., circle_packing)")
    run_parser.add_argument("--budget", type=int, default=50, help="Eval budget (default: 50)")
    run_parser.add_argument("--knob", action="append", default=[], help="OptKnob override: name=value")
    run_parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    run_parser.add_argument("--mock-llm", action="store_true", help="Use mock LLM for testing")
    run_parser.add_argument("--mock-responses", type=str, default=None, help="Path to JSON file with mock responses")
    run_parser.add_argument("--provider", choices=["mock", "openai", "vertex", "anthropic", "auto"], default="auto", help="LLM provider (default: auto-detect)")

    subparsers.add_parser("modes", help="List registered modes")

    tasks_parser = subparsers.add_parser("tasks", help="List available tasks")
    tasks_parser.add_argument("--category", default=None, help="Filter by category")

    lab_parser = subparsers.add_parser("lab", help="Run multiple modes on a task")
    lab_parser.add_argument("--task", required=True, help="Task name")
    lab_parser.add_argument("--modes", required=True, help="Comma-separated mode names")
    lab_parser.add_argument("--budget", type=int, default=150, help="Total budget across all modes")
    lab_parser.add_argument("--mock-llm", action="store_true", help="Use mock LLM")

    evolve_parser = subparsers.add_parser("evolve", help="Run MAP-Elites outer loop")
    evolve_parser.add_argument("--task", required=True, help="Task name")
    evolve_parser.add_argument("--generations", type=int, default=10, help="Number of generations")
    evolve_parser.add_argument("--budget", type=int, default=1000, help="Total budget")
    evolve_parser.add_argument("--mock-llm", action="store_true", help="Use mock LLM")

    validate_parser = subparsers.add_parser("validate", help="Validate trace fidelity")
    validate_parser.add_argument("--mode", required=True)
    validate_parser.add_argument("--task", required=True)
    validate_parser.add_argument("--baseline-trace", required=True, help="Path to Flora baseline trace")
    validate_parser.add_argument("--srf-trace", default=None, help="Path to SRF trace (default: latest)")

    args = parser.parse_args(argv)
    configure_logging()

    if args.command == "run":
        return _cmd_run(args)
    elif args.command == "modes":
        return _cmd_modes()
    elif args.command == "tasks":
        return _cmd_tasks(args)
    elif args.command == "lab":
        return _cmd_lab(args)
    elif args.command == "evolve":
        return _cmd_evolve(args)
    elif args.command == "validate":
        return _cmd_validate(args)
    else:
        parser.print_help()
        return 1


def _auto_create_llm_client():
    from srf._factory_shim import HttpxLLMClient, OpenAILLMClient, VertexAILLMClient

    if os.environ.get("OPENAI_API_KEY"):
        return OpenAILLMClient()
    if os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID"):
        return VertexAILLMClient()
    if os.environ.get("ANTHROPIC_API_KEY"):
        return HttpxLLMClient()
    raise ValueError(
        "No LLM API key found. Set OPENAI_API_KEY, ANTHROPIC_VERTEX_PROJECT_ID, "
        "or ANTHROPIC_API_KEY, or use --mock-llm."
    )


def _resolve_provider(args: argparse.Namespace) -> str:
    if args.mock_llm:
        return "mock"
    if args.provider != "auto":
        return args.provider
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID"):
        return "vertex"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "none"


def _cmd_run(args: argparse.Namespace) -> int:
    from srf._factory_shim import ExecutionContext, HttpxLLMClient, MockLLMClient, OpenAILLMClient, VertexAILLMClient, WorkflowExecutor
    from srf.ops.common.budget import init_budget
    from srf.ops.common.tracing import init_trace_dir
    from srf.ops.gepa.population import init_population
    from srf.ops.gepa.state import init_state
    from srf.registry import get_mode_registry, get_task_registry

    run_id = uuid.uuid4().hex[:12]
    configure_logging(harness=args.mode, task=args.task, run_id=run_id)
    log = structlog.get_logger()

    mode_registry = get_mode_registry()
    workflow = mode_registry.get(args.mode)
    if not workflow:
        print(f"Error: unknown mode '{args.mode}'. Available: {mode_registry.list_modes()}", file=sys.stderr)
        return 1

    task_registry = get_task_registry()
    task_config = task_registry.get(args.task)
    if not task_config:
        print(f"Error: unknown task '{args.task}'. Available: {task_registry.names()}", file=sys.stderr)
        return 1

    knobs = {k.name: k.default for k in workflow.knobs}
    for knob_str in args.knob:
        key, _, value = knob_str.partition("=")
        try:
            knobs[key] = float(value)
        except ValueError:
            knobs[key] = value

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path("outputs") / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = _resolve_provider(args)
    if provider == "mock":
        responses = None
        if args.mock_responses:
            responses = json.loads(Path(args.mock_responses).read_text())
        llm_client = MockLLMClient(responses=responses)
    elif provider == "openai":
        try:
            llm_client = OpenAILLMClient()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif provider == "vertex":
        try:
            llm_client = VertexAILLMClient()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif provider == "anthropic":
        try:
            llm_client = HttpxLLMClient()
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        print("Error: No LLM API key found. Set OPENAI_API_KEY, ANTHROPIC_VERTEX_PROJECT_ID, or ANTHROPIC_API_KEY, or use --mock-llm.", file=sys.stderr)
        return 1

    ctx = ExecutionContext(
        work_dir=output_dir,
        knobs=knobs,
        task=task_config,
        budget_limit=args.budget,
        llm_client=llm_client,
        run_id=run_id,
    )

    ctx.write_json("knobs.json", knobs)

    _copy_task_files(task_config, output_dir)

    init_trace_dir(output_dir)
    init_budget(ctx)

    modes_with_gepa_state = {"gepa", "scs", "aide", "ai_sci_v2", "openevolve", "shinka", "adaevolve", "evox", "autoresearch", "karpathy", "autoscientists", "ai_sci_v1"}
    if args.mode in modes_with_gepa_state:
        init_state(ctx)
        init_population(ctx)

    log.info(
        "run.start",
        mode=args.mode,
        task=args.task,
        budget=args.budget,
        knobs=knobs,
        output_dir=str(output_dir),
    )

    executor = WorkflowExecutor(ctx)
    executor.execute(workflow.root)

    budget_state = ctx.read_json("budget_state.json") or {}
    eval_count = budget_state.get("eval_count", 0)

    _STATE_FILES = {
        "best_of_n": "best_of_n_result.json",
        "scs": "scs_state.json",
        "aide": "aide_state.json",
        "ai_sci_v1": "autoresearch_state.json",
        "ai_sci_v2": "aide_state.json",
        "openevolve": "openevolve_state.json",
        "shinka": "shinka_state.json",
        "adaevolve": "adaevolve_state.json",
        "evox": "evox_state.json",
        "autoresearch": "autoresearch_state.json",
        "karpathy": "karpathy_state.json",
        "autoscientists": "autoscientists_state.json",
    }
    state_file = _STATE_FILES.get(args.mode, "gepa_state.json")
    state = ctx.read_json(state_file) or {}
    best_score = state.get("best_score", 0.0)

    log.info("run.complete", best_score=best_score, eval_count=eval_count)
    print(json.dumps({
        "run_id": run_id,
        "mode": args.mode,
        "task": args.task,
        "best_score": best_score,
        "eval_count": eval_count,
        "output_dir": str(output_dir),
    }, indent=2))
    return 0


def _copy_task_files(task_config: dict, output_dir: Path) -> None:
    task_dir = task_config.get("_dir")
    if not task_dir:
        return
    task_path = Path(task_dir)
    for fname in ["eval.py", "initial.py"]:
        src = task_path / fname
        if src.exists():
            shutil.copy2(src, output_dir / fname)


def _cmd_modes() -> int:
    from srf.registry import get_mode_registry

    registry = get_mode_registry()
    modes = registry.list_modes()
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
    if args.category:
        tasks = registry.list_by_category(args.category)
    else:
        tasks = registry.list_all()
    if not tasks:
        print("No tasks found.")
        return 0
    print("Available tasks:")
    for task in tasks:
        print(f"  - {task['name']} [{task.get('category', '?')}]: {task.get('description', '')[:80]}")
    return 0


def _cmd_lab(args: argparse.Namespace) -> int:
    from srf._factory_shim import MockLLMClient
    from srf.lab.director import LabDirector

    configure_logging()
    modes = [m.strip() for m in args.modes.split(",")]
    llm_client = MockLLMClient() if args.mock_llm else _auto_create_llm_client()
    director = LabDirector(llm_client=llm_client)
    report = director.run_lab(args.task, modes, args.budget)
    print(json.dumps(report, indent=2, default=str))
    return 0


def _cmd_evolve(args: argparse.Namespace) -> int:
    from srf._factory_shim import MockLLMClient
    from srf.lab.director import LabDirector
    from srf.lab.map_elites import MAPElitesLoop
    from srf.registry import get_mode_registry, get_task_registry

    configure_logging()
    registry = get_mode_registry()
    modes = registry.list_modes()
    knob_specs = {
        "temperature": [0.3, 0.5, 0.7, 0.9, 1.0],
        "parent_selection": ["best", "epsilon_greedy", "power_law", "uniform"],
    }

    loop = MAPElitesLoop(modes, knob_specs)
    llm_client = MockLLMClient() if args.mock_llm else _auto_create_llm_client()
    director = LabDirector(llm_client=llm_client)

    per_gen_budget = args.budget // args.generations if args.generations > 0 else args.budget

    for gen in range(args.generations):
        mode, knobs = loop.suggest()
        task_config = get_task_registry().get(args.task)
        if task_config is None:
            print(f"Error: unknown task '{args.task}'", file=sys.stderr)
            return 1
        result = director.run_mode(mode, task_config, per_gen_budget)
        loop.report(mode, knobs, result.score, per_gen_budget)

    report = loop.get_results()
    print(json.dumps(report, indent=2, default=str))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from srf.ops.common.trace_validator import validate_traces

    baseline_path = Path(args.baseline_trace)
    if not baseline_path.exists():
        print(f"Error: baseline trace not found: {baseline_path}", file=sys.stderr)
        return 1

    srf_path = Path(args.srf_trace) if args.srf_trace else None
    if srf_path and not srf_path.exists():
        print(f"Error: SRF trace not found: {srf_path}", file=sys.stderr)
        return 1

    report = validate_traces(baseline_path, srf_path)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
