"""Task definition protocol — Pydantic schema, eval contract, import allowlists."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class BudgetConfig(BaseModel):
    max_llm_tokens: int | None = None
    max_evals: int | None = None
    max_wall_time_s: int | None = None


class TaskDefinition(BaseModel):
    name: str
    category: str
    description: str
    initial_code: str
    eval_command: str = "python eval.py"
    metric: str = "score"
    maximize: bool = True
    allowed_imports: list[str] | None = None
    budget: BudgetConfig | None = None
    reference_score: float | None = None
    timeout: int = 30
    memory_limit_mb: int | None = None

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def coerce_timeout(cls, values: dict[str, Any]) -> dict[str, Any]:
        for key in ("timeout_s", "timeout"):
            if key in values and values[key] is not None:
                values["timeout"] = int(values[key])
        return values


def validate_eval_contract(eval_path: Path) -> list[str]:
    """AST-check that eval.py defines evaluate() or score() with expected signature."""
    errors: list[str] = []
    if not eval_path.exists():
        errors.append(f"eval file not found: {eval_path}")
        return errors

    try:
        tree = ast.parse(eval_path.read_text())
    except SyntaxError as e:
        errors.append(f"syntax error in {eval_path}: {e}")
        return errors

    func_names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_names.add(node.name)

    if "evaluate" not in func_names and "score" not in func_names:
        errors.append(f"{eval_path} must define evaluate() or score()")

    return errors


def check_import_allowlist(code: str, allowed: list[str] | None = None) -> list[str]:
    """Detect dynamic execution paths that bypass static analysis."""
    violations: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ("__import__", "exec", "eval"):
                violations.append(f"forbidden call: {func.id}()")
            elif isinstance(func, ast.Attribute):
                if (isinstance(func.value, ast.Name) and func.value.id == "importlib"
                        and func.attr == "import_module"):
                    violations.append("forbidden call: importlib.import_module()")

    return violations
