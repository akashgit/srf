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

    subparsers.add_parser("modes", help="List registered modes")

    tasks_parser = subparsers.add_parser("tasks", help="List available tasks")
    tasks_parser.add_argument("--category", default=None, help="Filter by category")

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
    elif args.command == "validate":
        return _cmd_validate(args)
    else:
        parser.print_help()
        return 1


def _cmd_run(args: argparse.Namespace) -> int:
    from srf._factory_shim import ExecutionContext, HttpxLLMClient, MockLLMClient, WorkflowExecutor
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

    if args.mock_llm:
        responses = None
        if args.mock_responses:
            responses = json.loads(Path(args.mock_responses).read_text())
        llm_client = MockLLMClient(responses=responses)
    else:
        try:
            llm_client = HttpxLLMClient()
        except ValueError as e:
            print(f"Error: {e}. Use --mock-llm for testing without an API key.", file=sys.stderr)
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

    state = ctx.read_json("gepa_state.json") or {}
    best_score = state.get("best_score", 0.0)
    eval_count = state.get("eval_count", 0)

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
