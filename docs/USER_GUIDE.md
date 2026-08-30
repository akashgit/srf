# SRF User Guide

SRF (Scientific Research Factory) reimplements 13 AI-driven scientific discovery harnesses as composable factory workflow Packages. A single research question can be refracted through multiple strategies, each with tunable OptKnobs that the outer loop evolves.

---

## Installation

Requires Python 3.12+.

```bash
# Base install (Anthropic direct API)
uv pip install -e '.'

# With Vertex AI support
uv pip install -e '.[vertex]'

# With OpenAI support
uv pip install -e '.[openai]'

# Both optional providers
uv pip install -e '.[vertex,openai]'
```

### Dependencies

**Base** (always installed):
- `structlog>=24.1.0`
- `pydantic>=2.10`
- `httpx[http2]>=0.27.0`

**Optional groups:**
- `openai` — `openai>=1.0`
- `vertex` — `google-auth>=2.0`, `anthropic[vertex]>=0.40`

---

## Quick Start

```bash
# Test everything works with mock LLM (no API key needed)
srf run --mode best_of_n --task circle_packing --budget 10 --mock-llm

# List all modes and tasks
srf modes
srf tasks

# Run with a real provider
export ANTHROPIC_VERTEX_PROJECT_ID="my-gcp-project"
srf run --mode gepa --task circle_packing --budget 50

# Compare modes head-to-head
srf lab --task circle_packing --modes gepa,aide,scs --budget 150

# Evolve knob configurations with MAP-Elites
srf evolve --task circle_packing --generations 20 --budget 1000
```

---

## CLI Reference

SRF has 6 subcommands. The entry point is `srf` (configured in `pyproject.toml` as `srf = "srf.cli:main"`).

### `srf run` — Run a mode on a task

The primary command. Executes a single mode's workflow DAG on a task.

```bash
srf run --mode gepa --task circle_packing --budget 50 --provider vertex
```

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | *required* | Mode name (e.g., `gepa`, `aide`, `best_of_n`) |
| `--task` | *required* | Task name (e.g., `circle_packing`) |
| `--budget` | `50` | Max eval iterations |
| `--knob key=val` | — | Override OptKnob values (repeatable) |
| `--provider` | `auto` | LLM provider: `vertex`, `openai`, `anthropic`, `mock`, or `auto` |
| `--mock-llm` | off | Use mock LLM (no API key needed) |
| `--mock-responses` | — | Path to JSON file with mock LLM responses |
| `--output-dir` | `outputs/<run_id>` | Where to write results |

**Output** (JSON to stdout):
```json
{
  "run_id": "abc123def456",
  "mode": "gepa",
  "task": "circle_packing",
  "best_score": 0.85,
  "eval_count": 42,
  "output_dir": "outputs/abc123def456"
}
```

**Knob overrides** let you tune mode behavior at the CLI:
```bash
srf run --mode gepa --task circle_packing \
  --knob temperature=0.9 \
  --knob parent_selection=epsilon_greedy
```

### `srf modes` — List registered modes

```bash
srf modes
```

Output:
```
Registered modes:
  - adaevolve
  - ai_sci_v1
  - ai_sci_v2
  - aide
  - autoresearch
  - autoscientists
  - best_of_n
  - evox
  - gepa
  - karpathy
  - openevolve
  - scs
  - shinka
```

### `srf tasks` — List available tasks

```bash
srf tasks
srf tasks --category math
```

| Flag | Default | Description |
|------|---------|-------------|
| `--category` | — | Filter by category |

Output:
```
Available tasks:
  - circle_packing [math]: Pack N circles into a unit square, maximizing sum of radii
  - autocorrelation_inequality [math]: Optimize autocorrelation inequality bounds
  - trimul [gpu]: Optimize triangular matrix multiplication kernels
```

### `srf lab` — Compare modes head-to-head

Runs multiple modes on the same task, splits budget evenly, and picks a winner.

```bash
srf lab --task circle_packing --modes gepa,aide,scs --budget 150 --mock-llm
```

| Flag | Default | Description |
|------|---------|-------------|
| `--task` | *required* | Task name |
| `--modes` | *required* | Comma-separated mode names |
| `--budget` | `150` | Total budget (split evenly across modes) |
| `--mock-llm` | off | Use mock LLM |

The budget is divided by the number of modes (e.g., 150 budget / 3 modes = 50 per mode). Modes run sequentially. The winner is selected by highest score.

### `srf evolve` — MAP-Elites knob evolution

Evolves mode + knob configurations over a 3D feature grid using MAP-Elites.

```bash
srf evolve --task circle_packing --generations 20 --budget 1000 --mock-llm
```

| Flag | Default | Description |
|------|---------|-------------|
| `--task` | *required* | Task to optimize |
| `--generations` | `10` | Number of evolution generations |
| `--budget` | `1000` | Total eval budget across all generations |
| `--mock-llm` | off | Use mock LLM |

Each generation, MAP-Elites suggests a (mode, knobs) pair, runs it, and reports the result. The 3D grid dimensions are:

1. **Harness type** (3 bins): population-based, agentic, sampling-based
2. **Search strategy** (4 bins): best, epsilon_greedy, power_law, uniform
3. **Budget bin** (3 bins): <=20, 21-50, >50 evals

Uses 30% random exploration and 70% improvement-based emission.

### `srf validate` — Compare traces

Validates SRF trace fidelity against a Flora baseline trace.

```bash
srf validate --mode gepa --task circle_packing --baseline-trace path/to/flora_trace.jsonl
srf validate --mode gepa --task circle_packing --baseline-trace path/to/flora.jsonl --srf-trace path/to/srf.jsonl
```

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | *required* | Mode name |
| `--task` | *required* | Task name |
| `--baseline-trace` | *required* | Path to Flora baseline trace |
| `--srf-trace` | — | Path to SRF trace (default: latest) |

---

## All 13 Modes

Modes are organized into three families by strategy type.

### Population-Based (Evolutionary)

| Mode | Strategy | When to Use |
|------|----------|-------------|
| `gepa` | Guided Evolution with Population Archive — reflective mutation + merge gating | Iterative refinement with stagnation recovery |
| `scs` | Stochastic Code Search — archive-based prompting with diversity | Broad exploration of solution space |
| `openevolve` | Multi-island MAP-Elites evolution | Diverse solution niches |
| `shinka` | Reflection + evolution — periodic self-reflection drives mutation | Learning from past failures |
| `adaevolve` | Adaptive 3-level hierarchy — meta-strategy vs normal evolution | Escaping local optima via radical restarts |
| `evox` | Meta-learned evolution — the search strategy itself evolves | Self-improving optimization |

### Agentic (Search-Based)

| Mode | Strategy | When to Use |
|------|----------|-------------|
| `aide` | Tree search — draft/improve/debug branches with backtracking | Problems needing structured debugging |
| `ai_sci_v2` | 4-stage BFTS pipeline — implementation, baseline, creative research, ablation | Full scientific workflow with staged depth |

### Sampling-Based

| Mode | Strategy | When to Use |
|------|----------|-------------|
| `best_of_n` | IID sampling — generate N solutions in parallel, pick the best | Quick baselines, embarrassingly parallel problems |
| `autoresearch` | Research-driven optimization — literature analysis before coding | Tasks benefiting from domain knowledge |
| `karpathy` | Autonomous agent with iterative tool use | Maximum autonomy, complex tasks |
| `autoscientists` | Multi-agent team — parallel scientists + merge agent | Combining diverse approaches |
| `ai_sci_v1` | Paper-writing loop — ideation, experimentation, writeup, review | End-to-end scientific discovery |

---

## Adding Your Own Task

Tasks live under `srf/tasks/<category>/<task_name>/` and are auto-discovered.

### Directory Structure

```
srf/tasks/
  math/
    circle_packing/
      task.yaml
      eval.py
      initial.py
  gpu/
    trimul/
      task.yaml
      eval.py
      initial.py
```

### task.yaml Schema

All fields of the `TaskDefinition` model (defined in `srf/tasks/schema.py`):

```yaml
name: my_task
category: math
description: "What the task optimizes"
initial_code: |
  def solve(n):
      return [0.5] * n
eval_command: "python eval.py"
metric: score
maximize: true
timeout: 30
reference_score: 1.0         # optional — Flora baseline score
allowed_imports:              # optional — restrict imports
  - numpy
  - scipy
memory_limit_mb: 512          # optional — memory limit for eval
budget:                       # optional — budget constraints
  max_llm_tokens: 100000
  max_evals: 50
  max_wall_time_s: 3600
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | str | yes | — | Task identifier (auto-derived from directory name if omitted) |
| `category` | str | yes | — | Category (auto-derived from parent directory name if omitted) |
| `description` | str | yes | — | What the task optimizes |
| `initial_code` | str | yes | — | Seed solution code |
| `eval_command` | str | no | `"python eval.py"` | Command to evaluate candidates |
| `metric` | str | no | `"score"` | Name of the metric to optimize |
| `maximize` | bool | no | `true` | Whether higher is better |
| `timeout` | int | no | `30` | Eval timeout in seconds |
| `reference_score` | float | no | — | Baseline score for comparison |
| `allowed_imports` | list | no | — | Import restrictions |
| `memory_limit_mb` | int | no | — | Memory limit for eval sandbox |
| `budget` | object | no | — | Budget constraints (see below) |

**Budget fields** (all optional):
- `max_llm_tokens` — Maximum total LLM tokens
- `max_evals` — Maximum number of eval runs
- `max_wall_time_s` — Maximum wall-clock time in seconds

### eval.py Contract

Your eval script **must** define either an `evaluate()` or `score()` function. SRF validates this at task discovery time using AST analysis (`srf/tasks/schema.py:43-64`).

The eval script must print a JSON line to stdout:

```json
{"score": 0.95, "metrics": {"accuracy": 0.98, "f1": 0.93}}
```

- `score` (float) — the primary metric (defaults to 0.0 if missing)
- `metrics` (dict) — optional additional metrics

SRF scans stdout in reverse for the last JSON line starting with `{`. This means your eval can print debugging output before the result.

### initial.py

The seed solution. This file is copied into the working directory at the start of each run.

### Verify Your Task

```bash
# Check it appears in the registry
srf tasks --category math

# Validate traces against a baseline
srf validate --mode gepa --task my_task --baseline-trace path/to/baseline.jsonl
```

---

## Provider Setup

SRF supports four LLM providers. Provider auto-detection checks environment variables in order: `OPENAI_API_KEY` -> `ANTHROPIC_VERTEX_PROJECT_ID` -> `ANTHROPIC_API_KEY`.

### Vertex AI (Claude via Google Cloud)

```bash
uv pip install -e '.[vertex]'
export ANTHROPIC_VERTEX_PROJECT_ID="my-gcp-project"
export CLOUD_ML_REGION="us-east5"   # optional, default is us-east5

srf run --mode gepa --task circle_packing --provider vertex
```

Model mapping: `sonnet` -> `claude-sonnet-4-6`, `opus` -> `claude-opus-4-6`, `haiku` -> `claude-haiku-4-5`

The region `"global"` is automatically normalized to `"us-east5"`.

### OpenAI

```bash
uv pip install -e '.[openai]'
export OPENAI_API_KEY="sk-..."

srf run --mode gepa --task circle_packing --provider openai
```

Model mapping: `sonnet` -> `gpt-4o-mini`, `opus` -> `gpt-4o`, `haiku` -> `gpt-4o-mini`

### Anthropic (Direct API)

```bash
uv pip install -e '.'
export ANTHROPIC_API_KEY="sk-ant-..."

srf run --mode gepa --task circle_packing --provider anthropic
```

Model mapping: `sonnet` -> `claude-sonnet-4-20250514`, `opus` -> `claude-opus-4-20250514`, `haiku` -> `claude-haiku-4-5-20251001`

### Mock (Testing)

```bash
srf run --mode gepa --task circle_packing --mock-llm
```

No API key needed. Returns a stub `solve()` function by default. For custom responses, provide a JSON file:

```bash
srf run --mode gepa --task circle_packing --mock-llm --mock-responses responses.json
```

---

## Environment Variables

| Variable | Required For | Description |
|----------|-------------|-------------|
| `OPENAI_API_KEY` | OpenAI provider | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic provider | Anthropic direct API key |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Vertex AI provider | Google Cloud project ID |
| `CLOUD_ML_REGION` | Vertex AI (optional) | GCP region (default: `us-east5`). `"global"` normalized to `"us-east5"` |
| `SRF_OTLP_ENDPOINT` | Telemetry (optional) | OTLP gRPC endpoint (e.g., `http://localhost:4317`). If unset, telemetry is a no-op |
| `SRF_WORK_DIR` | Internal | Set by WorkflowExecutor for gate evaluator commands |

---

## Output Format and Files

Each `srf run` creates an output directory (default: `outputs/<run_id>`) with the following files:

### Core Files

| File | Description |
|------|-------------|
| `knobs.json` | OptKnob values used for this run |
| `budget_state.json` | Budget consumption state |
| `best_solution.py` | Best candidate solution found |
| `eval.py` | Eval script (copied from task directory) |
| `initial.py` | Seed solution (copied from task directory, if exists) |

### Mode-Specific State Files

Each mode writes its own state file:

| Mode | State File |
|------|------------|
| `gepa` | `gepa_state.json` |
| `best_of_n` | `best_of_n_result.json` |
| `scs` | `scs_state.json` |
| `aide` | `aide_state.json` |
| `ai_sci_v1` | `autoresearch_state.json` |
| `ai_sci_v2` | `aide_state.json` |
| `openevolve` | `openevolve_state.json` |
| `shinka` | `shinka_state.json` |
| `adaevolve` | `adaevolve_state.json` |
| `evox` | `evox_state.json` |
| `autoresearch` | `autoresearch_state.json` |
| `karpathy` | `karpathy_state.json` |
| `autoscientists` | `autoscientists_state.json` |

### Trace Files (JSONL)

Five structured log files for debugging and analysis:

| File | Contents |
|------|----------|
| `evaluations.jsonl` | Candidate evaluation records |
| `candidates.jsonl` | Candidate generation records |
| `llm_calls.jsonl` | LLM call token usage |
| `policy_decisions.jsonl` | Policy decision events |
| `budget.jsonl` | Budget consumption snapshots |

### Structured Logs

SRF uses `structlog` for JSON-formatted logs to stderr. Key events:
- `run.start` — mode, task, budget, knobs, output directory
- `run.complete` — best score, eval count

---

## Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `Error: unknown mode 'xyz'` | Invalid `--mode` value | Run `srf modes` to see valid options |
| `Error: unknown task 'xyz'` | Invalid `--task` value | Run `srf tasks` to see valid options |
| `Error: No LLM API key found` | No provider env vars set | Set an API key or use `--mock-llm` |
| `Error: OPENAI_API_KEY required` | OpenAI provider without key | Set `OPENAI_API_KEY` |
| `Error: ANTHROPIC_API_KEY required` | Anthropic provider without key | Set `ANTHROPIC_API_KEY` |
| `Error: baseline trace not found` | Invalid `--baseline-trace` path | Check the file path exists |

---

## Sandbox

Candidate code runs in an isolated sandbox during evaluation. SRF supports three backends:

| Backend | When Used | Requirements |
|---------|-----------|-------------|
| `auto` (default) | Uses Firejail if available, else subprocess | Firejail optional |
| `firejail` | Forced Firejail | `firejail` installed |
| `gvisor` | Google gVisor container | `runsc` installed |
| `none` | No sandboxing | — |

**Firejail resource limits:**
- Max processes: 32
- Max open files: 32
- Max file size: 2 MB
- Max address space: ~1 GB
- Network: disabled
- Filesystem: isolated to temp directory

**gVisor:** Runs with `--network=none --rootless` (no root required). Falls back to subprocess if `runsc` is not found.

---

## Hack Detection

SRF includes AST-based hack detection (`srf/ops/common/hack_detect.py`) to catch candidate solutions that game the eval rather than solving the problem. Five categories are checked:

| Category | Weight | What It Catches |
|----------|--------|-----------------|
| Hardcoded output | 0.3 | `return <constant>` with non-trivial values |
| Forbidden imports | 0.2 | `os`, `subprocess`, `shutil`, `socket`, `http`, `urllib`, `requests`, `ctypes` |
| File I/O | 0.2 | `open()`, pathlib operations |
| Monkey patching | 0.2 | `sys.modules`, `builtins.__import__`, `builtins.open` |
| Test data access | 0.1 | Attribute access containing both "eval" and "data" |

A weighted composite score > 0.3 flags the candidate as suspicious.
