# SRF — Scientific Research Factory

SRF reimplements 13 AI-driven scientific discovery harnesses (from Flora Jia's harness-comparison benchmark) as composable factory workflow Packages. A single research question can be refracted through multiple strategies, each with tunable OptKnobs that the outer loop evolves.

## Quick Start

```bash
uv pip install -e '.[vertex]'

# Run a mode on a task
srf run --mode gepa --task circle_packing --budget 50 --provider vertex

# Run with mock LLM (no API key needed — for testing)
srf run --mode gepa --task circle_packing --budget 10 --mock-llm

# List available modes and tasks
srf modes
srf tasks
```

## Modes

All 13 harnesses are implemented. Each builds a Package DAG from factory primitives (FnNode, LLMNode, Loop, Conditional).

| Mode | Strategy | Best For |
|------|----------|----------|
| `best_of_n` | IID sampling — generate N solutions in parallel, pick the best | Quick baselines, embarrassingly parallel problems |
| `scs` | Stochastic Code Search — archive-based prompting with diversity | Broad exploration of solution space |
| `gepa` | Guided Evolution with Population Archive — reflective mutation + merge gating | Iterative refinement with stagnation recovery |
| `aide` | Tree search — draft/improve/debug branches with backtracking | Problems needing structured debugging |
| `ai_sci_v2` | 4-stage BFTS pipeline — implementation, baseline, creative research, ablation | Full scientific workflow with staged depth |
| `openevolve` | Multi-island MAP-Elites evolution | Diverse solution niches |
| `shinka` | Reflection + evolution — periodic self-reflection drives mutation | Learning from past failures |
| `adaevolve` | Adaptive 3-level hierarchy — meta-strategy vs normal evolution | Escaping local optima via radical restarts |
| `evox` | Meta-learned evolution — the search strategy itself evolves | Self-improving optimization |
| `autoresearch` | Research-driven optimization — literature analysis before coding | Tasks benefiting from domain knowledge |
| `karpathy` | Autonomous agent with iterative tool use | Maximum autonomy, complex tasks |
| `autoscientists` | Multi-agent team — parallel scientists + merge agent | Combining diverse approaches |
| `ai_sci_v1` | Paper-writing loop — ideation, experimentation, writeup, review | End-to-end scientific discovery |

## CLI Reference

```
srf run       --mode <mode> --task <task> [options]    Run a single mode on a task
srf modes                                              List registered modes
srf tasks     [--category <cat>]                       List available tasks
srf lab       --task <task> --modes a,b,c [options]    Compare modes head-to-head
srf evolve    --task <task> [options]                   MAP-Elites knob evolution
srf validate  --mode <m> --task <t> --baseline-trace <path>  Compare traces
```

### `srf run` flags

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | required | Mode name (e.g., `gepa`, `aide`, `best_of_n`) |
| `--task` | required | Task name (e.g., `circle_packing`) |
| `--budget` | 50 | Max eval iterations |
| `--knob key=val` | — | Override OptKnob values (repeatable) |
| `--provider` | auto | `vertex`, `openai`, `anthropic`, or `auto` |
| `--mock-llm` | off | Use mock LLM (no API key needed) |
| `--output-dir` | `outputs/<run_id>` | Where to write results |

### `srf lab` — compare modes

```bash
srf lab --task circle_packing --modes gepa,aide,scs --budget 150 --mock-llm
```

Splits budget evenly across modes, runs each, and reports a winner with per-mode scores.

### `srf evolve` — MAP-Elites knob evolution

```bash
srf evolve --task circle_packing --generations 20 --budget 1000 --mock-llm
```

Evolves mode + knob configurations over a 3D feature grid (harness type × search strategy × eval budget). Uses random and improvement emitters to explore the joint space.

| Flag | Default | Description |
|------|---------|-------------|
| `--task` | required | Task to optimize |
| `--generations` | 10 | Number of evolution generations |
| `--budget` | 1000 | Total eval budget across all generations |
| `--mock-llm` | off | Use mock LLM |

## Available Tasks

| Task | Category | Description |
|------|----------|-------------|
| `circle_packing` | math | Pack N circles into a unit square, maximizing sum of radii |
| `autocorrelation_inequality` | math | Optimize autocorrelation inequality bounds |
| `trimul` | gpu | Optimize triangular matrix multiplication kernels |

## Adding a Task

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
reference_score: 1.0    # optional — Flora baseline
```

```python
# eval.py — scores candidate.py, prints {"score": float}
# initial.py — seed solution copied into the working directory
```

Validate with:

```bash
srf validate --mode gepa --task my_task --baseline-trace path/to/flora_trace.jsonl
```

The task registry auto-discovers tasks from the directory structure.

## Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| **Modes** | `srf/modes/` | One `.py` per harness — builds a Package DAG from factory primitives |
| **Ops** | `srf/ops/` | Python callables for FnNode — domain logic (eval, mutation, selection) |
| **Tasks** | `srf/tasks/` | Benchmark problems with `task.yaml` + `eval.py` + `initial.py` |
| **Lab Director** | `srf/lab/director.py` | Multi-mode orchestration — run and compare modes on a task |
| **MAP-Elites** | `srf/lab/map_elites.py` | Outer loop evolving mode + knob configurations |
| **Tracing** | `srf/ops/common/tracing.py` | Structured trace logging (JSONL) for each run |
| **Budget** | `srf/ops/common/budget.py` | Eval budget tracking and gating |
| **Hack Detection** | `srf/ops/common/` | Detects shortcut solutions that game the eval |
| **Telemetry** | `srf/logging/` | Structured logging via structlog |
| **Memory** | `srf/_factory_shim.py` | MemoryDeclaration for cross-iteration context |

Modes compose Packages from Ops. The executor walks the DAG, calling Ops and LLM nodes in sequence, respecting Loop gates and Conditional branches.

## Provider Setup

| Provider | Install | Env Vars |
|----------|---------|----------|
| Vertex AI | `uv pip install -e '.[vertex]'` | `ANTHROPIC_VERTEX_PROJECT_ID`, `GOOGLE_CLOUD_PROJECT` |
| OpenAI | `uv pip install -e '.[openai]'` | `OPENAI_API_KEY` |
| Anthropic | `uv pip install -e '.'` | `ANTHROPIC_API_KEY` |
| Mock | `uv pip install -e '.'` | — (use `--mock-llm`) |

Provider auto-detection (`--provider auto`, the default): SRF checks for `OPENAI_API_KEY`, then `ANTHROPIC_VERTEX_PROJECT_ID`, then `ANTHROPIC_API_KEY` in that order.

## Adding a Mode

1. Create `srf/modes/{name}.py` with a `build_{name}_workflow() -> Workflow` function
2. Build your DAG from factory primitives: `FnNode`, `LLMNode`, `Loop`, `Sequential`, `Conditional`
3. Implement ops in `srf/ops/{name}/`
4. The mode registry auto-discovers any module in `srf/modes/` that exports the builder function

## License

Internal project — not for redistribution.
