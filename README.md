# SRF — Scientific Research Factory

SRF reimplements 13 AI-driven scientific discovery harnesses (from Flora Jia's harness-comparison benchmark) as composable factory workflow Packages. A single research question can be refracted through multiple strategies, each with tunable OptKnobs that the outer loop evolves.

## Quick Start

```bash
pip install -e .

# Run with Vertex AI
srf run --mode gepa --task circle_packing --budget 10 --provider vertex

# Run with OpenAI
srf run --mode gepa --task circle_packing --budget 10 --provider openai

# Run with mock LLM (no API key needed — for testing)
srf run --mode gepa --task circle_packing --budget 10 --mock-llm
```

Provider auto-detection: if `--provider` is omitted, SRF checks for `OPENAI_API_KEY`, `ANTHROPIC_VERTEX_PROJECT_ID`, then `ANTHROPIC_API_KEY` in that order.

## Architecture

Three layers on top of remote-factory primitives:

| Layer | Location | Purpose |
|-------|----------|---------|
| **Modes** | `srf/modes/` | One `.py` per harness — builds a Package DAG from factory primitives (FnNode, LLMNode, Loop, Conditional) |
| **Ops** | `srf/ops/` | Python callables referenced by `FnNode.callable_name` — domain logic for each mode |
| **Tasks** | `srf/tasks/` | Benchmark problems with `task.yaml` + `eval.py` + `initial.py` |

Modes compose Packages from Ops. The executor walks the DAG, calling Ops and LLM nodes in sequence, respecting Loop gates and Conditional branches.

## GEPA Mode

GEPA (Guided Evolution with Population Archive) is an evolutionary code-improvement loop:

```
Loop(budget_gate):
  Conditional(merge_decision):
    PROCEED → mutate(select_parent → reflective_prompt → LLM)
    RELOOP  → merge(find_candidates → merge_prompt → LLM)
  eval(sandbox → accept_or_reject)
```

Each iteration either mutates the best program or merges top candidates when progress stagnates. Acceptance criteria, parent selection strategy, and merge thresholds are all tunable via OptKnobs.

## Available Tasks

| Task | Category | Description |
|------|----------|-------------|
| `circle_packing` | math | Pack N circles into a unit square, maximizing sum of radii |
| `autocorrelation_inequality` | math | Optimize autocorrelation inequality bounds |
| `trimul` | gpu | Optimize triangular matrix multiplication kernels |

## CLI Commands

```bash
srf run --mode <mode> --task <task> [--budget N] [--knob key=val] [--provider <p>] [--mock-llm]
srf modes                          # List registered modes
srf tasks [--category <cat>]       # List available tasks
srf validate --mode <m> --task <t> --baseline-trace <path>  # Compare traces
```

## Provider Options

| Provider | Flag | Env Var Required |
|----------|------|------------------|
| OpenAI | `--provider openai` | `OPENAI_API_KEY` |
| Vertex AI | `--provider vertex` | `ANTHROPIC_VERTEX_PROJECT_ID` |
| Anthropic | `--provider anthropic` | `ANTHROPIC_API_KEY` |
| Mock | `--mock-llm` | — |

Optional dependencies: `pip install -e ".[openai]"` or `pip install -e ".[vertex]"`.

## Adding a New Task

Create `srf/tasks/{category}/{name}/` with three files:

```yaml
# task.yaml
name: my_task
category: math
description: "What the task optimizes"
initial_code: |
  def solve(...):
      ...
eval_command: "python eval.py"
metric: score
maximize: true
timeout: 30
```

```python
# eval.py — scores candidate.py, prints {"score": float}
# initial.py — seed solution copied into the working directory
```

The task registry auto-discovers tasks from the directory structure.

## Adding a New Mode

1. Create `srf/modes/{name}.py` with a `build_{name}_workflow() -> Workflow` function
2. Build your DAG from factory primitives: `FnNode`, `LLMNode`, `Loop`, `Sequential`, `Conditional`
3. Implement ops in `srf/ops/{name}/`
4. The mode registry auto-discovers any module in `srf/modes/` that exports the builder function

## Planned Modes (13 Harnesses)

| # | Mode | Strategy |
|---|------|----------|
| 1 | **GEPA** | Reflective mutation + gating |
| 2 | OpenEvolve | Multi-island MAP-Elites |
| 3 | AIDE | Tree search (draft/improve/debug) |
| 4 | AI Scientist V2 | 4-stage BFTS pipeline |
| 5 | Best-of-N | IID sampling |
| 6 | AutoResearch | Research-driven optimization |
| 7 | AutoResearch Karpathy | Claude Code agent |
| 8 | AutoScientists | Multi-agent team |
| 9 | AdaEvolve | Adaptive evolution |
| 10 | EvoX Meta | Meta-learned evolution |
| 11 | SCS | Archive-based prompting |
| 12 | ShinkaEvolve | Reflection + evolution |
| 13 | The AI Scientist | Paper-writing loop |

Phase 1 implements GEPA with 3 benchmark tasks. Remaining modes follow in Phase 2.

## License

Internal project — not for redistribution.
