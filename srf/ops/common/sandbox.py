"""Sandboxed eval runner — Firejail with subprocess+resource fallback."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class EvalResult:
    score: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    stdout: str = ""
    stderr: str = ""


def _has_firejail() -> bool:
    return shutil.which("firejail") is not None


def run_eval(ctx: Any) -> None:
    """Execute eval.py on candidate.py in a sandbox, write eval_result.json."""
    work_dir: Path = ctx.work_dir
    candidate_path = work_dir / "candidate.py"
    task_config = ctx.task

    if not candidate_path.exists():
        result = EvalResult(error="candidate.py not found")
        ctx.write_json("eval_result.json", _result_to_dict(result))
        return

    eval_command = task_config.get("eval_command", "python eval.py")
    timeout = task_config.get("timeout", 30)

    task_dir_str = task_config.get("_dir")
    if task_dir_str:
        task_dir = Path(task_dir_str)
    else:
        task_name = task_config.get("name", "")
        task_category = task_config.get("category", "")
        task_dir = _find_task_dir(task_category, task_name)

    with tempfile.TemporaryDirectory(prefix="srf_eval_") as tmpdir:
        tmp = Path(tmpdir)
        shutil.copy2(candidate_path, tmp / "candidate.py")
        if task_dir and (task_dir / "eval.py").exists():
            shutil.copy2(task_dir / "eval.py", tmp / "eval.py")
        if task_dir and (task_dir / "initial.py").exists():
            shutil.copy2(task_dir / "initial.py", tmp / "initial.py")

        result = _execute_in_sandbox(tmp, eval_command, timeout)

    ctx.write_json("eval_result.json", _result_to_dict(result))
    logger.info(
        "sandbox.eval_complete",
        score=result.score,
        error=result.error,
        iteration=ctx.iteration,
    )


def _find_task_dir(category: str, name: str) -> Path | None:
    candidates = [
        Path(__file__).parent.parent.parent / "tasks" / category / name,
        Path("srf") / "tasks" / category / name,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _execute_in_sandbox(tmp: Path, eval_command: str, timeout: int) -> EvalResult:
    if _has_firejail():
        return _run_firejail(tmp, eval_command, timeout)
    return _run_subprocess(tmp, eval_command, timeout)


def _run_firejail(tmp: Path, eval_command: str, timeout: int) -> EvalResult:
    cmd = [
        "firejail",
        "--quiet",
        "--seccomp=socket",
        "--rlimit-nproc=32",
        "--rlimit-nofile=32",
        "--rlimit-fsize=2m",
        "--rlimit-as=1096m",
        "--net=none",
        f"--private={tmp}",
        sys.executable,
    ] + eval_command.split()[1:]

    return _run_process(cmd, tmp, timeout)


def _run_subprocess(tmp: Path, eval_command: str, timeout: int) -> EvalResult:
    cmd = [sys.executable] + eval_command.split()[1:]
    return _run_process(cmd, tmp, timeout)


def _run_process(cmd: list[str], cwd: Path, timeout: int) -> EvalResult:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout,
            env=env,
        )
        if proc.returncode != 0:
            return EvalResult(
                error=f"exit code {proc.returncode}: {proc.stderr.strip()[:500]}",
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        return _parse_eval_output(proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired:
        return EvalResult(error=f"timeout after {timeout}s")
    except Exception as e:
        return EvalResult(error=str(e))


def _parse_eval_output(stdout: str, stderr: str) -> EvalResult:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                return EvalResult(
                    score=float(data.get("score", 0.0)),
                    metrics=data.get("metrics", {}),
                    stdout=stdout,
                    stderr=stderr,
                )
            except (json.JSONDecodeError, ValueError):
                continue
    return EvalResult(error="no valid JSON output from eval", stdout=stdout, stderr=stderr)


def _result_to_dict(result: EvalResult) -> dict:
    return {
        "score": result.score,
        "metrics": result.metrics,
        "error": result.error,
    }
