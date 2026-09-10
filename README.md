# SRF — Scientific Research Factory

SRF reimplements 13 AI-driven scientific discovery harnesses (from Flora Jia's
harness-comparison benchmark) as **composable refactory workflow Packages**. A single
research question can be refracted through multiple strategies, each with tunable
`OptKnob`s that an outer loop can evolve.

## SRF is a pure package

SRF declares **semantics**: the graph of each harness, its deterministic ops, and its
tasks. It ships **no runtime** — no executor, no LLM client, no node loop. The DSH
workflow spine is the only thing that walks an SRF graph.

The handoff is `Workflow.to_dict()` → one `graph.json` per mode:

```
srf/modes/*.py  ──build──▶  Workflow (refactory flat DAG)  ──to_dict──▶  graph.json  ──▶  DSH spine
```

A graph is a **flat DAG**: a table of typed nodes plus labelled edges. Study loops are
not nesting — they are a `reloop` edge from a gate back to the loop body's entry.
Alternative branches (AIDE's draft/improve/debug, GEPA's mutate/merge) are gate-named
edge conditions.

## Quick Start

```bash
uv pip install -e .

# What is in the package
srf modes
srf tasks

# Emit the graph IR the runtime loads
srf graphs --out graphs
srf graph --mode gepa

# Load every emitted graph into the real DSH spine and walk it to completion
srf probe --graphs graphs
```

SRF has no `run` command: `srf run` prints the pointer to the runtime. Executing a mode
is the DSH spine's job (`dsh science run --mode <mode> --task <task>` — see the project's
`PLAN.md`, Phase 4).

## Modes

All 13 harnesses are implemented as flat DAGs built from refactory's vocabulary.

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
srf modes                                       List registered modes
srf tasks     [--category <cat>]                List available tasks
srf graph     --mode <mode> [--out <path>]      Emit one mode's graph.json
srf graphs    [--out <dir>]                     Emit every mode's graph.json
srf probe     [--graphs <dir>] [--spine <url>]  Load the graphs into the DSH spine
srf run                                         Prints where the runtime lives
```

### `srf probe` — the boundary test

`srf probe` reads the emitted `graph.json` files exactly as the runtime does, validates
them, and then drives the real spine to completion, taking every gate outcome in turn.
It exits non-zero if any graph fails to load, fails validation, stalls, or contains a
node the walk never reaches.

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

The task registry auto-discovers tasks from the directory structure.

## Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| **Modes** | `srf/modes/` | One `.py` per harness — composes refactory `Package`s into a flat DAG |
| **Packaging** | `srf/packaging.py` | Node/package/loop builders shared by every mode |
| **Graphs** | `srf/graphs.py` | Emits `graph.json` — the boundary with the runtime |
| **Ops** | `srf/ops/` | Deterministic Python steps the graph's `FnNode`s name |
| **Tasks** | `srf/tasks/` | Benchmark problems with `task.yaml` + `eval.py` + `initial.py` |
| **MAP-Elites** | `srf/lab/map_elites.py` | Knob/topology search used by the outer loop (Phase 5) |
| **Tracing** | `srf/ops/common/tracing.py` | Structured trace logging (JSONL) for each run |
| **Budget** | `srf/ops/common/budget.py` | Eval budget tracking and gating |
| **Hack Detection** | `srf/ops/common/` | Detects shortcut solutions that game the eval |
| **Telemetry** | `srf/logging/` | Structured logging via structlog |

A mode composes `Package`s from nodes and deterministic ops; `Package.compile()` lowers
the composition to the flat `Workflow` IR; `Workflow.to_dict()` serializes it. Loops
become a gate's `reloop` edge, branches become gate-named edge conditions, and
parallelism becomes `ForkNode` / `JoinNode`.

A node's `reads` / `writes` declarations are the interface to its op: the op resolves
its own input and output filenames from the node that invoked it, so two branches of a
fork never collide on an artifact. `tests/test_mode_graphs.py` enforces that every
declared read is written by an ancestor.

## Adding a Mode

1. Create `srf/modes/{name}.py` with `build_{name}_workflow() -> Workflow`, plus
   `build_{name}_knobs()` and `build_{name}_memory()`.
2. Build the body with `srf.packaging` helpers: `chain`, `single`, `op`, `llm`, `agent`,
   `gate`, `eval_step`, `Sequential`, `Conditional`, `Parallel`, `loop`, `budget_gate`.
3. Start the graph with `task_input()` (writes the problem and the run settings) and, for
   a stateful loop, `seed_run([...])` (gives the search a starting point).
4. Finish with `compile_mode("<name>", declared(root, knobs=KNOBS, memory=MEMORY))`.
5. Implement any new deterministic steps in `srf/ops/{name}/`.
6. Run `srf graphs && srf probe`, and `pytest tests/test_mode_graphs.py`.

The mode registry auto-discovers any module in `srf/modes/` that exports the builder.

## License

Internal project — not for redistribution.
