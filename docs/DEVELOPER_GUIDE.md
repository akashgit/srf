# SRF Developer Guide

How to extend SRF: create modes, tasks, ops, providers, and integrate with the meta-optimization layer.

---

## Creating a New Mode (Step-by-Step)

A mode is a single Python file in `srf/modes/` that defines a workflow DAG. No manual registration is needed — the `ModeRegistry` auto-discovers it by convention.

### Step 1: Create the Mode File

```bash
touch srf/modes/my_mode.py
```

The filename determines the mode name. `my_mode.py` becomes mode `my_mode`.

### Step 2: Import Primitives

All DAG primitives live in `srf/_factory_shim.py`:

```python
from __future__ import annotations

from srf._factory_shim import (
    # Control flow
    Sequential,
    Parallel,
    Loop,
    Conditional,

    # Execution nodes
    FnNode,
    LLMNode,
    GateNode,
    AgentNode,

    # Composition
    Package,
    Edge,
    Port,
    StateContract,

    # Workflow top-level
    Workflow,
    OptKnob,
    MemoryDeclaration,
)
```

### Step 3: Implement the Three Required Functions

Every mode implements exactly 3 functions following the naming convention `build_<mode_name>_*`:

```python
def build_my_mode_knobs() -> list[OptKnob]:
    """Tunable parameters for this mode."""
    ...

def build_my_mode_memory() -> list[MemoryDeclaration]:
    """Memory namespaces this mode uses."""
    ...

def build_my_mode_workflow() -> Workflow:
    """Build and return the complete workflow DAG."""
    ...
```

Only `build_my_mode_workflow()` is required for auto-discovery, but all three are the standard convention used by every existing mode.

### Step 4: Define Knobs

```python
def build_my_mode_knobs() -> list[OptKnob]:
    return [
        OptKnob(
            name="temperature",
            kind="threshold",
            default=0.7,
            bounds=[0.3, 0.5, 0.7, 0.9, 1.0],
            node_id="generate",
            description="LLM sampling temperature",
        ),
        OptKnob(
            name="strategy",
            kind="prompt",
            default="greedy",
            bounds=["greedy", "exploratory", "balanced"],
            node_id="select_strategy",
            description="Search strategy mode",
        ),
    ]
```

### Step 5: Define Memory

```python
def build_my_mode_memory() -> list[MemoryDeclaration]:
    return [
        MemoryDeclaration(namespace="my_mode.state", kind="kv", retention="run"),
        MemoryDeclaration(namespace="my_mode.history", kind="log", retention="run"),
    ]
```

### Step 6: Build the Workflow

```python
def build_my_mode_workflow() -> Workflow:
    prompt_builder = FnNode(
        name="build_prompt",
        callable_name="srf.ops.my_mode.prompts:build_prompt",
        reads={"task.yaml", "state.json"},
        writes={"prompt.md"},
    )

    generate = LLMNode(
        name="generate",
        model="sonnet",
        temperature=0.7,
        system_prompt="You are a code generator. Output a single fenced code block.",
        reads={"prompt.md"},
        writes={"candidate.py"},
    )

    eval_node = FnNode(
        name="sandbox_eval",
        callable_name="srf.ops.common.sandbox:run_eval",
        reads={"candidate.py", "task.yaml"},
        writes={"eval_result.json"},
    )

    gen_pkg = Package(
        name="my_mode-generate",
        nodes=[prompt_builder, generate],
        edges=[Edge(source="build_prompt", target="generate")],
        inputs=[Port("task", "task.yaml")],
        outputs=[Port("candidate", "candidate.py")],
        state_contract=StateContract(
            requires={"task.yaml", "state.json"},
            produces={"candidate.py"},
        ),
    )

    iteration = Sequential(
        name="my_mode-iteration",
        children=[gen_pkg, eval_node],
    )

    budget_gate = GateNode(
        name="budget_check",
        evaluator_command="python -m srf.ops.common.budget check",
    )

    main_loop = Loop(
        name="my_mode",
        body=iteration,
        gate=budget_gate,
        max_iterations=100,
    )

    return Workflow(
        name="my_mode",
        root=main_loop,
        knobs=build_my_mode_knobs(),
        memory=build_my_mode_memory(),
    )
```

### Step 7: Create Op Functions

```bash
mkdir -p srf/ops/my_mode
touch srf/ops/my_mode/__init__.py
touch srf/ops/my_mode/prompts.py
```

```python
# srf/ops/my_mode/prompts.py
def build_prompt(task: dict, state: dict) -> str:
    """Build LLM prompt from task and state."""
    return f"Task: {task}\nState: {state}"
```

### Step 8: Test It

```python
from srf.registry import get_mode_registry

registry = get_mode_registry()
workflow = registry.get("my_mode")
print(workflow.name)   # "my_mode"
print(workflow.knobs)  # [OptKnob(...), ...]
```

From the CLI:
```bash
srf modes  # should list "my_mode"
srf run --mode my_mode --task circle_packing --budget 10 --mock-llm
```

### File Checklist

```
srf/modes/my_mode.py
  ├── build_my_mode_knobs() -> list[OptKnob]
  ├── build_my_mode_memory() -> list[MemoryDeclaration]
  └── build_my_mode_workflow() -> Workflow

srf/ops/my_mode/
  ├── __init__.py
  ├── prompts.py
  └── (other op modules as needed)
```

---

## How Mode Registration Works

The `ModeRegistry` class (`srf/registry.py`) auto-discovers modes with zero configuration.

### Discovery Algorithm

```python
class ModeRegistry:
    def _discover(self) -> None:
        import srf.modes as modes_pkg
        modes_path = Path(modes_pkg.__file__).parent
        for finder, name, ispkg in pkgutil.iter_modules([str(modes_path)]):
            module = importlib.import_module(f"srf.modes.{name}")
            builder_name = f"build_{name}_workflow"
            if hasattr(module, builder_name):
                self._modes[name] = getattr(module, builder_name)
```

The convention is:

1. All `.py` files in `srf/modes/` are scanned via `pkgutil.iter_modules`
2. Each module is imported as `srf.modes.{name}`
3. The registry looks for a function named `build_{name}_workflow`
4. If found, the function is stored as `self._modes[name]`

**Example flow:**
```
File: srf/modes/gepa.py
  -> Module name: "gepa"
  -> Looks for: "build_gepa_workflow"
  -> Found at gepa.py line 194
  -> Registered as: modes["gepa"] = build_gepa_workflow
```

If a module fails to import, the error is logged and the module is skipped — it won't crash the registry.

---

## DAG Primitives

All 13 primitives are dataclasses defined in `srf/_factory_shim.py`.

### Control Flow

| Primitive | Fields | Description |
|-----------|--------|-------------|
| `Sequential` | `name`, `children` | Execute children in order |
| `Parallel` | `name`, `children` | Execute children concurrently |
| `Loop` | `name`, `body`, `gate`, `max_iterations` (default 500) | Repeat body until gate or max iterations |
| `Conditional` | `name`, `gate`, `branches` | Branch based on gate outcome |

### Execution Nodes

| Primitive | Fields | Description |
|-----------|--------|-------------|
| `FnNode` | `name`, `callable_name`, `reads`, `writes` | Call a Python function |
| `LLMNode` | `name`, `model`, `temperature`, `system_prompt`, `reads`, `writes` | Call an LLM |
| `GateNode` | `name`, `evaluator_command` | Decision point — evaluator returns branch name |
| `AgentNode` | `name`, `model`, `system_prompt`, `max_turns` (default 10), `reads`, `writes` | Multi-turn agentic LLM |

### Composition

| Primitive | Fields | Description |
|-----------|--------|-------------|
| `Package` | `name`, `nodes`, `edges`, `inputs`, `outputs`, `state_contract`, `knobs`, `memory` | Group nodes with edges, I/O ports, and contract |
| `Edge` | `source`, `target` | Directed edge between node names |
| `Port` | `name`, `file_pattern` | Named input/output with file pattern |
| `StateContract` | `requires`, `produces` | Declare required/produced files |
| `Workflow` | `name`, `root`, `knobs`, `memory` | Top-level container |

### Usage Examples from Existing Modes

**Sequential** (from `gepa.py`):
```python
iteration = Sequential(
    name="gepa-iteration",
    children=[action_pkg, eval_pkg],
)
```

**Parallel** (from `best_of_n.py`):
```python
parallel_gen = Parallel(
    name="parallel-generate",
    children=gen_eval_packages,
)
```

**Loop with gate** (from `gepa.py`):
```python
gepa_loop = Loop(
    name="gepa",
    body=iteration,
    gate=budget_gate,
    max_iterations=500,
)
```

**Conditional with branches** (from `gepa.py`):
```python
action_pkg = Conditional(
    name="gepa-action",
    gate=merge_gate,
    branches={"PROCEED": mutate_pkg, "RELOOP": merge_pkg},
)
```

**Package with edges and contract** (from `gepa.py`):
```python
return Package(
    name="gepa-mutate",
    nodes=[select_parent, build_reflective, generate_code],
    edges=[
        Edge(source="select_parent", target="build_reflective_prompt"),
        Edge(source="build_reflective_prompt", target="generate_code"),
    ],
    inputs=[Port("population", "population.json")],
    outputs=[Port("candidate", "candidate.py")],
    state_contract=StateContract(
        requires={"population.json", "task.yaml"},
        produces={"candidate.py"},
    ),
)
```

---

## Wiring FnNode to Python Functions

FnNode uses a `callable_name` string in `"module.path:function_name"` format:

```
"srf.ops.gepa.population:select_parent"
 └────────────┬──────────┘ └─────┬──────┘
        Python module        Function name
```

At execution time, this resolves to:
```python
from srf.ops.gepa.population import select_parent
```

### Organizational Convention

- **Mode-specific ops:** `srf.ops.<mode_name>.<module>:function`
- **Shared ops:** `srf.ops.common.<module>:function`

### Examples from the Codebase

| callable_name | Resolves to |
|---------------|-------------|
| `srf.ops.gepa.population:select_parent` | `from srf.ops.gepa.population import select_parent` |
| `srf.ops.gepa.prompts:build_reflective_prompt` | `from srf.ops.gepa.prompts import build_reflective_prompt` |
| `srf.ops.common.sandbox:run_eval` | `from srf.ops.common.sandbox import run_eval` |
| `srf.ops.aide.ops:search_policy` | `from srf.ops.aide.ops import search_policy` |

### File Layout

```
srf/ops/
  common/          # Shared across all modes
    sandbox.py     # run_eval
    budget.py      # Budget tracking
    tracing.py     # Trace logging
    hack_detect.py # Hack detection
    ...
  gepa/            # GEPA-specific ops
    population.py
    prompts.py
    merge.py
    acceptance.py
    state.py
  aide/            # AIDE-specific ops
    ops.py
  best_of_n/       # Best-of-N-specific ops
    ...
```

---

## OptKnobs

OptKnobs parameterize node behavior and are evolved by the MAP-Elites outer loop.

### Schema

```python
@dataclass
class OptKnob:
    name: str         # Unique identifier
    kind: str         # "threshold" or "prompt"
    default: Any      # Default value
    bounds: list[Any] # Search space
    node_id: str      # Which node this knob affects
    description: str  # Human-readable description (optional, default "")
```

### Knob Kinds

**Threshold** — numeric values (continuous/discrete):
```python
OptKnob(
    name="temperature",
    kind="threshold",
    default=0.7,
    bounds=[0.3, 0.5, 0.7, 0.9, 1.0],
    node_id="generate_code",
    description="LLM sampling temperature",
)
```

**Prompt** — categorical string values:
```python
OptKnob(
    name="parent_selection",
    kind="prompt",
    default="best",
    bounds=["best", "pareto", "epsilon_greedy"],
    node_id="select_parent",
    description="How parents are chosen for mutation",
)
```

### How Knobs Wire to Nodes

The `node_id` field matches a node's `name` field in the DAG. At runtime, the executor reads knob values from the optimization controller and applies them to matching nodes.

```python
# Knob targets the LLMNode named "generate_code"
OptKnob(name="temperature", ..., node_id="generate_code")

# This LLMNode will receive the knob value
LLMNode(name="generate_code", model="sonnet", temperature=0.7, ...)
```

### CLI Override

Users can override knob values at the CLI:
```bash
srf run --mode gepa --task circle_packing --knob temperature=0.9 --knob parent_selection=epsilon_greedy
```

---

## MemoryDeclarations and the MemoryBackend

Modes declare persistent state namespaces via `MemoryDeclaration`.

### Schema

```python
@dataclass
class MemoryDeclaration:
    namespace: str  # Dot-separated (e.g., "gepa.population")
    kind: str       # "kv", "log", or "graph"
    retention: str  # "run", "experiment", or "permanent"
```

### Memory Kinds

| Kind | Pattern | Example |
|------|---------|---------|
| `kv` | Key-value store | `gepa.population` — stores candidate programs indexed by ID |
| `log` | Append-only log | `gepa.rejections` — tracks rejected attempts |
| `graph` | Graph structure | `gepa.genealogy` — tracks parent-child lineage |

### Retention Policies

| Policy | Lifetime |
|--------|----------|
| `run` | Single workflow execution (most common) |
| `experiment` | Persists across runs in the same experiment |
| `permanent` | Persists indefinitely |

### Namespace Convention

Use `"<mode_name>.<purpose>"`:
```python
MemoryDeclaration(namespace="gepa.population", kind="kv", retention="run")
MemoryDeclaration(namespace="gepa.genealogy", kind="graph", retention="run")
MemoryDeclaration(namespace="gepa.rejections", kind="log", retention="run")
```

### Memory Access via Nodes

Nodes declare memory dependencies through their `reads` and `writes` sets:

```python
accept = FnNode(
    name="accept_or_reject",
    callable_name="srf.ops.gepa.acceptance:accept_or_reject",
    reads={"eval_result.json", "candidate.py", "selected_parent.json",
           "population.json", "genealogy.json", "gepa_state.json"},
    writes={"population.json", "genealogy.json", "rejection_history.json",
            "accepted_history.json", "gepa_state.json", "best_solution.py"},
)
```

---

## Creating Shared Ops

Shared ops live in `srf/ops/common/` and are used across multiple modes.

### Existing Shared Ops

| Module | Key Functions | Used By |
|--------|---------------|---------|
| `srf.ops.common.sandbox` | `run_eval` | All modes (sandbox evaluation) |
| `srf.ops.common.budget` | `init_budget`, budget gate | All modes (budget tracking) |
| `srf.ops.common.tracing` | `init_trace_dir` | All modes (JSONL tracing) |
| `srf.ops.common.hack_detect` | `analyze_code`, `check_candidate` | Modes with hack detection |
| `srf.ops.common.selection` | Selection strategies | Population-based modes |
| `srf.ops.common.prompts` | Prompt builders | Multiple modes |
| `srf.ops.common.reflection` | Reflection utilities | Reflective modes |
| `srf.ops.common.population` | Population management | Population-based modes |
| `srf.ops.common.state_files` | State file naming | All modes |

### Using Shared Ops in Your Mode

Reference them via `callable_name`:
```python
eval_node = FnNode(
    name="sandbox_eval",
    callable_name="srf.ops.common.sandbox:run_eval",
    reads={"candidate.py", "task.yaml"},
    writes={"eval_result.json"},
)
```

---

## Creating a New Task

### Step 1: Create the Directory

```bash
mkdir -p srf/tasks/math/my_task
```

### Step 2: Write task.yaml

```yaml
name: my_task
category: math
description: "Optimize function f(x) to minimize error"
initial_code: |
  def solve(x):
      return x * 2
eval_command: "python eval.py"
metric: score
maximize: true
timeout: 30
```

### Step 3: Write eval.py

Must define `evaluate()` or `score()`. Must print JSON to stdout.

```python
import json

def evaluate(candidate_path="candidate.py"):
    # Load and run the candidate
    with open(candidate_path) as f:
        code = f.read()
    
    namespace = {}
    exec(code, namespace)
    solve = namespace["solve"]
    
    # Score it
    result = solve(42)
    score = 1.0 / (1.0 + abs(result - 84))
    
    print(json.dumps({"score": score, "metrics": {"result": result}}))

if __name__ == "__main__":
    evaluate()
```

### Step 4: Write initial.py

```python
def solve(x):
    return x * 2
```

### Step 5: Verify

```bash
srf tasks --category math  # should show my_task
srf run --mode best_of_n --task my_task --budget 5 --mock-llm
```

### Task Discovery

The `TaskRegistry` (`srf/tasks/registry.py`) discovers tasks via `rglob("task.yaml")`:
- Task name = directory name
- Category = parent directory name
- Both are auto-populated in the config if omitted from `task.yaml`

---

## Creating a New Eval Script

### Contract

The eval script must:

1. **Define** either `evaluate()` or `score()` (validated by AST analysis in `srf/tasks/schema.py`)
2. **Print** a JSON line to stdout: `{"score": <float>, "metrics": {...}}`

The function can have any parameters and return type — only the name is validated.

### Output Parsing

SRF scans stdout in reverse for the last line starting with `{` (`srf/ops/common/sandbox.py:193-207`). This means your eval can print debug output before the JSON result:

```python
print("Debug: running evaluation...")
print("Debug: candidate loaded successfully")
print(json.dumps({"score": 0.95, "metrics": {"accuracy": 0.98}}))
```

If no valid JSON is found, the eval returns an error with score 0.0.

---

## Adding a New LLM Provider

LLM providers are defined in `srf/_factory_shim.py`. Each provider implements a `generate()` method.

### Provider Interface

```python
class MyProvider:
    MODEL_MAP = {
        "sonnet": "my-model-small",
        "opus": "my-model-large",
        "haiku": "my-model-tiny",
    }

    def __init__(self):
        # Initialize client
        ...

    def generate(
        self, system_prompt: str, user_prompt: str, model: str, temperature: float
    ) -> LLMResponse:
        # Call your API
        resolved_model = self.MODEL_MAP.get(model, model)
        # ... make API call ...
        return LLMResponse(content=response_text, input_tokens=N, output_tokens=M)
```

### Registration

Add your provider to `_resolve_provider()` in `srf/cli.py`:

```python
def _resolve_provider(args):
    # ... existing checks ...
    if os.environ.get("MY_PROVIDER_KEY"):
        return "my_provider"
    # ... fallthrough ...
```

And to the provider initialization block:

```python
if provider == "my_provider":
    llm_client = MyProvider()
```

### Existing Providers

| Provider | Class | Required Env Var | Model Map |
|----------|-------|-----------------|-----------|
| Anthropic | `HttpxLLMClient` | `ANTHROPIC_API_KEY` | sonnet->claude-sonnet-4-20250514, opus->claude-opus-4-20250514, haiku->claude-haiku-4-5-20251001 |
| OpenAI | `OpenAILLMClient` | `OPENAI_API_KEY` | sonnet->gpt-4o-mini, opus->gpt-4o, haiku->gpt-4o-mini |
| Vertex AI | `VertexAILLMClient` | `ANTHROPIC_VERTEX_PROJECT_ID` | sonnet->claude-sonnet-4-6, opus->claude-opus-4-6, haiku->claude-haiku-4-5 |
| Mock | `MockLLMClient` | — | Returns canned responses |

---

## Adding a New Sandbox Backend

Sandbox backends are defined in `srf/ops/common/sandbox.py`. The `_execute_in_sandbox()` function dispatches by backend name.

### Adding a Backend

1. Create a `_run_mybackend()` function following the existing pattern:

```python
def _run_mybackend(tmp: Path, eval_command: str, timeout: int) -> EvalResult:
    cmd = ["mybackend", "--isolate", str(tmp), sys.executable] + eval_command.split()[1:]
    return _run_process(cmd, tmp, timeout)
```

2. Add the dispatch case in `_execute_in_sandbox()`:

```python
elif backend == "mybackend":
    return _run_mybackend(tmp, eval_command, timeout)
```

### Existing Backends

| Backend | Command | Resource Limits |
|---------|---------|----------------|
| `firejail` | `firejail --quiet --seccomp=socket --net=none ...` | 32 procs, 32 files, 2MB file size, 1GB RAM, no network |
| `gvisor` | `runsc do --network=none --rootless ...` | No network, rootless |
| `none` | Direct `subprocess` | No isolation |
| `auto` | Firejail if available, else subprocess | Depends on what's found |

---

## How Hack Detection Works

Hack detection (`srf/ops/common/hack_detect.py`) uses a three-tier pipeline:

- **Tier 1:** AST visitor checks five categories (always runs)
- **Tier 2:** Held-out evaluation when AST flags suspicious code
- **Tier 3:** LLM review (deferred/not yet implemented)

### Five Detection Categories

```python
@dataclass
class HackSignals:
    hardcoded_output: float = 0.0    # weight: 0.3
    forbidden_imports: float = 0.0   # weight: 0.2
    file_io: float = 0.0            # weight: 0.2
    monkey_patching: float = 0.0    # weight: 0.2
    test_data_access: float = 0.0   # weight: 0.1
```

Composite score = weighted sum. Threshold for "suspicious" is > 0.3.

### What Each Category Catches

1. **Hardcoded output** — `return <constant>` where the constant is non-zero, non-one numeric
2. **Forbidden imports** — `os`, `subprocess`, `shutil`, `socket`, `http`, `urllib`, `requests`, `ctypes`
3. **File I/O** — `open()`, pathlib operations, any `.open()` method
4. **Monkey patching** — `sys.modules`, `builtins.__import__`, `builtins.open`, subscript on `sys.modules`
5. **Test data access** — attribute access containing both "eval" and "data" (heuristic)

### Public API

```python
from srf.ops.common.hack_detect import analyze_code, check_candidate

# Get raw signals
signals = analyze_code(code_string)
print(signals.composite_score)
print(signals.is_suspicious)  # True if composite_score > 0.3

# Check with threshold
is_clean, signals = check_candidate(code_string, threshold=0.3)
```

### Using in Your Mode

Add a hack check node after candidate generation:

```python
hack_check = FnNode(
    name="hack_check",
    callable_name="srf.ops.common.hack_detect:check_candidate",
    reads={"candidate.py"},
    writes={"hack_signals.json"},
)
```

---

## Telemetry Integration

SRF uses OpenTelemetry for distributed tracing (`srf/telemetry/provider.py`).

### Setup

Set `SRF_OTLP_ENDPOINT` and install opentelemetry:

```bash
export SRF_OTLP_ENDPOINT="http://localhost:4317"
uv pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
```

### Graceful Degradation

If the endpoint is unset or opentelemetry is not installed, SRF uses a no-op tracer with zero overhead. No code changes needed — it "just works" in both modes.

### Using Spans in Your Code

```python
from srf.telemetry.provider import span

with span("my_operation", attributes={"mode": "gepa", "iteration": 5}) as s:
    # ... your code ...
    s.set_attribute("result", "success")
```

### Resource Attributes

All spans are tagged with:
- `service.name`: "srf"
- `srf.run_id`: unique run identifier
- `srf.mode`: mode name
- `srf.task`: task name

### Initialization

Telemetry is initialized automatically via:

```python
from srf.telemetry.provider import init_telemetry

tracer = init_telemetry(service_name="srf", run_id="abc123", mode="gepa", task="circle_packing")
```

---

## Lab Director

The Lab Director (`srf/lab/director.py`) orchestrates multi-mode execution and comparison.

### Protocol

```python
class LabDirectorProtocol(ABC):
    @abstractmethod
    def select_mode(self, task: dict[str, Any]) -> str: ...

    @abstractmethod
    def run_mode(self, mode: str, task: dict[str, Any], budget: int) -> ModeResult: ...

    @abstractmethod
    def compare_results(self, results: list[ModeResult]) -> ModeResult: ...
```

### ModeResult

```python
@dataclass
class ModeResult:
    score: float
    best_code: str
    trace_path: Path
    cost: float
    knob_values_used: dict[str, Any] = field(default_factory=dict)
```

### How It Works

1. **Mode selection**: `select_mode()` returns the first available mode (stub — to be enhanced)
2. **Execution**: `run_mode()` creates a temp directory, initializes knobs to defaults, copies task files, creates an `ExecutionContext`, and runs the `WorkflowExecutor`
3. **Comparison**: `compare_results()` selects the result with the highest score

### Multi-Mode Runs

`run_lab()` executes multiple modes on a task:

```python
director = LabDirector(llm_client=my_client)
report = director.run_lab(
    task_name="circle_packing",
    modes=["gepa", "aide", "scs"],
    budget=150,
)
```

Budget is split evenly across modes. Modes run sequentially. The report includes per-mode scores and a winner:

```json
{
  "task": "circle_packing",
  "modes": {
    "gepa": {"score": 0.85, "trace_path": "/tmp/srf_lab_gepa_..."},
    "aide": {"score": 0.72, "trace_path": "/tmp/srf_lab_aide_..."},
    "scs": {"score": 0.91, "trace_path": "/tmp/srf_lab_scs_..."}
  },
  "winner": "scs",
  "winner_score": 0.91
}
```

### Mode State Initialization

`_init_mode_state()` handles mode-specific setup:
- **GEPA**: imports and runs `init_population()` and `init_state()` from GEPA ops
- **All others**: copies `initial_code` from the task to `best_solution.py`

### Extending the Lab Director

To implement smarter mode selection, override `select_mode()`:

```python
class SmartLabDirector(LabDirector):
    def select_mode(self, task: dict[str, Any]) -> str:
        # Use task features to pick the best mode
        if task.get("category") == "math":
            return "gepa"
        return "aide"
```

---

## MAP-Elites for Orchestration

MAP-Elites (`srf/lab/map_elites.py`) evolves mode + knob configurations across a behavioral feature grid.

### Grid Structure

The grid is 3D with dimensions (3, 4, 3) = 36 total cells:

**Dimension 1 — Harness type (3 bins):**

| Bin | Modes |
|-----|-------|
| 0 (population-based) | gepa, scs, openevolve, shinka, adaevolve, evox |
| 1 (agentic) | aide, ai_sci_v2 |
| 2 (sampling-based) | best_of_n, autoresearch, karpathy, autoscientists, ai_sci_v1 |

**Dimension 2 — Search strategy (4 bins):**

| Bin | Strategy |
|-----|----------|
| 0 | best |
| 1 | epsilon_greedy |
| 2 | power_law |
| 3 | uniform |

**Dimension 3 — Budget bin (3 bins):**

| Bin | Budget Range |
|-----|-------------|
| 0 | <= 20 evals |
| 1 | 21-50 evals |
| 2 | > 50 evals |

### Update Rule

A cell is updated only if empty or the new score exceeds the current occupant:

```python
def update(self, cell: MAPElitesCell) -> bool:
    key = cell.features
    if key not in self.cells or cell.score > self.cells[key].score:
        self.cells[key] = cell
        return True
    return False
```

### Emitters

**RandomEmitter** — 30% of the time (or when grid is empty):
- Random mode from available modes
- Random knob values from specs

**ImprovementEmitter** — 70% of the time:
- Pick a random occupied cell
- Deep-copy its knob values
- Mutate one random knob to a new value
- Return the parent's mode with mutated knobs

### Evolution Loop

```python
loop = MAPElitesLoop(
    modes=["gepa", "aide", "scs"],
    knob_specs={
        "temperature": [0.3, 0.5, 0.7, 0.9, 1.0],
        "parent_selection": ["best", "epsilon_greedy", "power_law", "uniform"],
    },
)

# Each generation
mode, knobs = loop.suggest()
# ... run mode with knobs, get score ...
updated = loop.report(mode, knobs, score=0.85, budget=50)

# Get final results
results = loop.get_results()
print(results["coverage"])  # fraction of cells filled (0.0 to 1.0)
print(results["best"])      # best cell across the grid
```

### CLI Usage

```bash
srf evolve --task circle_packing --generations 20 --budget 1000 --mock-llm
```

The CLI configures MAP-Elites with these knob specs:
- `temperature`: [0.3, 0.5, 0.7, 0.9, 1.0]
- `parent_selection`: ["best", "epsilon_greedy", "power_law", "uniform"]

Budget is divided evenly across generations.

---

## Testing Your Changes

### Verify mode registration

```bash
srf modes  # should list your new mode
```

### Run with mock LLM

```bash
srf run --mode my_mode --task circle_packing --budget 5 --mock-llm
```

### Check output files

```bash
ls outputs/<run_id>/
# Should contain: knobs.json, budget_state.json, eval.py, trace files, etc.
```

### Validate task schema

```python
from srf.tasks.schema import TaskDefinition
import yaml

with open("srf/tasks/math/my_task/task.yaml") as f:
    config = yaml.safe_load(f)

task = TaskDefinition(**config)  # Raises on invalid schema
```

### Validate eval contract

```python
from srf.tasks.schema import validate_eval_contract
from pathlib import Path

errors = validate_eval_contract(Path("srf/tasks/math/my_task/eval.py"))
assert not errors, f"Eval contract errors: {errors}"
```

### Test hack detection

```python
from srf.ops.common.hack_detect import check_candidate

is_clean, signals = check_candidate("def solve(): return 42")
print(is_clean, signals.composite_score)
```

### Run the test suite

```bash
python -m pytest tests/ -v
```
