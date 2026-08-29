# Factory Configuration — SRF (Scientific Research Factory)

## Goal

Build SRF — a scientific research factory that reimplements 13 AI-driven scientific discovery harnesses (from Flora Jia's harness-comparison benchmark) as composable factory workflow Packages on top of remote-factory's Package ecosystem. A single research question can be refracted through multiple strategies, each with tunable OptKnobs that the outer loop evolves.

## Scope

### Modifiable Files

```
srf/**/*.py
tests/**/*.py
pyproject.toml
srf/tasks/**/task.yaml
srf/tasks/**/eval.py
srf/tasks/**/initial.py
docs/**/*.md
```

### Off-Limits Files

```
.factory/**
factory.md
CLAUDE.md
eval/score.py
.github/**
```

## Guards

- Do not delete or overwrite existing tests — tests may be extended, never removed
- Do not introduce secrets or credentials — no API keys, tokens, or passwords in the repo
- Do not modify files outside the declared scope
- All mode Packages must expose the uniform interface: inputs=[Port("task", "task.yaml")], outputs=[Port("best_solution", "best_solution.py"), Port("trace", "trace.jsonl")]
- Every FnNode callable must be importable via its `callable_name` path
- LLMNode model references must use factory-supported model names (sonnet, opus, haiku)
- OptKnob bounds must be non-empty lists with the default value included
- StateContract.requires and .produces must accurately reflect file I/O

## Eval

### Eval Command

```bash
python eval/score.py
```

### Threshold

0.6

### Eval Spec

```json
[
  "Build and run the project's primary entry point without errors"
]
```

### Eval Dimensions

| Dimension | Weight | Parser | Description |
|-----------|--------|--------|-------------|
| syntax_check | 0.833 | exit_code | Verify code has no syntax errors |
| observability | 0.167 | json | Analyze logging coverage, structured logging, and request tracing |

## Smoke Test

```bash
python -c "import srf; print('SRF imported successfully')"
```

## Target Branch

main

## Project Eval

<!-- Project-specific eval dimensions will be added after GEPA mode validates -->
<!-- Candidates: score_parity (SRF vs Flora baselines), behavioral_fidelity (trace analysis), cost_parity (token usage comparison) -->

## Architecture

Three layers in SRF, one imported from factory:

| Layer | Location | Purpose |
|-------|----------|---------|
| Modes | `srf/modes/` | One `.py` per harness — each builds a Package from factory primitives |
| Ops | `srf/ops/` | Python callables referenced by FnNode.callable_name — domain logic |
| Tasks | `srf/tasks/` | Task definitions with task.yaml + eval.py — benchmark problems |
| Lab | `srf/lab/` | Phase 2 — Lab Director agent for multi-mode orchestration |

## Implementation Phases

### Phase 1: Scaffolding + GEPA

1. Repo scaffolding — pyproject.toml, CLI entry point, mode registry, task registry
2. Common infrastructure — eval sandbox, budget tracking, tracing, code parsing
3. GEPA mode — Package definition + all domain callables
4. Port 3 benchmark tasks — circle_packing, autocorrelation_inequality, trimul
5. Test GEPA — graph validation, compile round-trip, knob mutation, e2e
6. Validate — run GEPA on ported tasks, compare to Flora's baselines

**Success criterion:** GEPA mode achieves >= 95% of Flora's GEPA scores on the 3 validation tasks with comparable LLM cost.

### Phase 2: Remaining Modes

Priority order: OpenEvolve, AIDE, AI Scientist V2, then the remaining 9 modes.

### Phase 3: Lab Director

Multi-mode orchestration agent that dispatches research problems across modes.
