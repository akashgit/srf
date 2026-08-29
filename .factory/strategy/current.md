## Build Plan — SRF (Scientific Research Factory)

### Vision

SRF reimplements 13 AI-driven scientific discovery harnesses (from Flora Jia's harness-comparison benchmark) as composable factory workflow Packages on top of remote-factory's Package ecosystem. A single research question can be refracted through multiple strategies, each with tunable OptKnobs that the outer loop evolves — making SRF a harness discovery platform, not just a harness collection.

### Architecture

- **Language/Runtime**: Python 3.12+ — all harness implementations, ops callables, and benchmark tasks are Python. The factory ecosystem is Python-native.
- **Framework**: remote-factory Package primitives (`Package`, `Sequential`, `Parallel`, `Conditional`, `Loop`, `FnNode`, `LLMNode`, `GateNode`, `OptKnob`, `Port`, `MemoryDeclaration`, `StateContract`) — imported from `factory.workflow.primitives` and `factory.workflow.package`. Research confirms no benefit from adding Prefect/Dagster/Temporal (tech-stack report: "Do NOT adopt external orchestrators").
- **Data Storage**: Filesystem-based (`trace.jsonl`, `task.yaml`, `best_solution.py`, `population.json`, `genealogy.json`, `gepa_state.json`). No database for Phase 1.
- **Key Libraries**:
  - `remote-factory` — Package ecosystem (pip dependency, provides all DAG primitives: `Sequential`, `Parallel`, `Conditional`, `Loop`, `FnNode`, `LLMNode`, `GateNode`, `OptKnob`, `Port`, `MemoryDeclaration`, `StateContract`, `Edge`, `Workflow`)
  - `structlog` — structured JSON logging with experiment context binding (80% faster parsing, CNCF standard)
  - `pydantic>=2.10` — Rust-backed validation for Pydantic models wrapping factory primitives (5-50x faster than v1)
  - `httpx[http2]` — async LLM client with connection pooling and HTTP/2 multiplexing (no vendor lock-in)

### Observations

- Current composite score: 0.0 (greenfield project, no source files yet)
- Weakest eval dimension: observability (0.0%) — 0/0 functions have logging, no structured logging, no request tracing
- No prior experiments — first build cycle
- Graph: 8 nodes, 6 edges (eval infrastructure only), no SRF source code exists yet

### Phase 1: Project scaffold + eval harness

#### H1: SRF package scaffold with registry, common ops, eval sandbox, budget tracking, tracing, and Pydantic models

- **Category:** EXPLORE
- **Growth dimension:** capability_surface
- **Backlog item:** SRF scientific research factory - 13 harnesses as composable factory Packages
- **What:**
  - Create `pyproject.toml` with dependencies: `remote-factory`, `structlog`, `pydantic>=2.10`, `httpx[http2]`, `opentelemetry-api`, `opentelemetry-sdk`. CLI entry point: `srf = srf.cli:main`
  - Create `srf/__init__.py` with version and package metadata (enables smoke test: `python -c "import srf"`)
  - Create `srf/cli.py` — CLI entry point supporting:
    - `srf run --mode gepa --task circle_packing --budget 50`
    - `srf run --mode gepa --task circle_packing --knob temperature=0.9 --knob parent_selection=pareto`
    - `srf modes` — list registered modes
    - `srf tasks` / `srf tasks --category math` — list available tasks
  - Create `srf/registry.py` — `ModeRegistry` (maps mode names to Package builders, auto-discovers `srf/modes/*.py`) and `TaskRegistry` (discovers tasks by directory convention under `srf/tasks/`)
  - Create `srf/ops/common/sandbox.py` — sandboxed eval runner:
    - `async def run_eval(candidate_path, task, timeout=30, memory_limit_mb=512) -> EvalResult`
    - Copies `candidate.py` into temp dir with `eval.py`, runs as subprocess with Firejail isolation (`--seccomp=socket --rlimit-nproc=32 --rlimit-nofile=32 --rlimit-fsize=2m --rlimit-as=1096m --net=none`), parses stdout JSON `{"score": float, "metrics": {...}}`, returns `EvalResult(score, metrics, error)`. Falls back to `subprocess.run` with `resource` module limits if Firejail unavailable
  - Create `srf/ops/common/budget.py` — budget tracking:
    - `check` callable (used as `GateNode` evaluator: `python -m srf.ops.common.budget check`) — reads mode state JSON, returns RELOOP if LLM cost + eval count within budget, PROCEED if done
    - Tracks two resources: **LLM cost** (token counts from API responses, ingesting `usage.input_tokens` and `usage.output_tokens` — NOT client-side estimates per Pitfall 4.1) and **eval count** (number of sandbox evaluations)
    - Budget limits set in `task.yaml` or via CLI flags
  - Create `srf/ops/common/tracing.py` — structured JSONL trace emission:
    - Emits Flora-compatible 5-file trace format: `evaluations.jsonl`, `candidates.jsonl`, `llm_calls.jsonl`, `policy_decisions.jsonl`, `budget.jsonl`
    - Uses structlog with JSON renderer, ISO timestamps, experiment context binding (`harness`, `task`, `run_id`, `knobs`)
  - Create `srf/ops/common/code_parsing.py` — extract fenced code blocks from LLM output
  - Create `srf/logging/config.py` — structlog configuration: JSON renderer, ISO timestamps, file output to `srf/logs/{harness}_{task}_{run_id}.jsonl`
  - Create `srf/lab/__init__.py` and `srf/lab/protocol.py` — seams only for Phase 2 Lab Director: `ModeResult(score, best_code, trace_path, cost, knob_values_used)` and `LabDirectorProtocol` abstract class
  - Create `srf/tasks/__init__.py` and `srf/tasks/registry.py` — task lookup by name/category, directory convention: `srf/tasks/{category}/{task_name}/` containing `task.yaml`, `eval.py`, `initial.py`
  - Create `tests/test_common_sandbox.py` — sandbox blocks `import os/subprocess/socket`, respects timeout, returns correct exit codes, handles OOM
  - Create `tests/test_task_registry.py` — task discovery, schema validation
  - **All infrastructure designed to be extensible for all 13 modes** — the mode registry, Port interface, StateContract pattern, and sandbox are mode-agnostic
- **Why:** Research confirms remote-factory primitives are the correct DAG layer (tech-stack report). Firejail is adequate for Phase 1 sandboxing (tech-stack: "fastest to implement, adequate for controlled benchmark tasks"). structlog is the 2026 Python standard for structured logging. Budget tracker must ingest API-returned token counts, not estimates (Pitfall 4.1: "client-side estimates diverge from billing"). The Lab Director protocol seams (`ModeResult`, `LabDirectorProtocol`) ensure Phase 2 integration without implementing it now.
- **Expected impact:** syntax_check 0.0→1.0 (valid Python across all files), observability 0.0→0.7 (structlog in all ops, JSON output, context binding), capability_surface +0.3 (core infrastructure operational)
- **Priority:** high

### Phase 2: GEPA mode — faithful Package implementation

#### H2: GEPA mode with exact Package structure, all ops callables, 5 OptKnobs, and MemoryDeclarations

- **Category:** EXPLORE
- **Growth dimension:** capability_surface
- **Backlog item:** SRF scientific research factory - 13 harnesses as composable factory Packages
- **What:**
  - Create `srf/modes/gepa.py` — builds the GEPA Package using exact factory primitives from the design spec. The complete workflow graph:

    ```
    Loop(name="gepa", max_iterations=500)
    │
    ├── body = Sequential(name="gepa-iteration")
    │   │
    │   ├── Conditional(name="gepa-action")
    │   │   │
    │   │   ├── gate: merge_decision (GateNode, evaluator_command="python -m srf.ops.gepa.decision should_merge")
    │   │   │
    │   │   ├── PROCEED → Package("gepa-mutate")
    │   │   │   ├── select_parent      (FnNode, callable_name="srf.ops.gepa.population:select_parent")
    │   │   │   ├── build_reflective   (FnNode, callable_name="srf.ops.gepa.prompts:build_reflective_prompt")
    │   │   │   └── generate_code      (LLMNode, model="sonnet", temperature=0.7)
    │   │   │
    │   │   └── RELOOP → Package("gepa-merge")
    │   │       ├── find_merge_candidates (FnNode, callable_name="srf.ops.gepa.merge:find_triplet_or_top2")
    │   │       ├── build_merge_prompt    (FnNode, callable_name="srf.ops.gepa.prompts:build_merge_prompt")
    │   │       └── generate_merge        (LLMNode, model="sonnet", temperature=0.7)
    │   │
    │   └── Package("gepa-eval")
    │       ├── sandbox_eval        (FnNode, callable_name="srf.ops.common.sandbox:run_eval")
    │       └── accept_or_reject    (FnNode, callable_name="srf.ops.gepa.acceptance:accept_or_reject")
    │
    └── gate: budget_check (GateNode, evaluator_command="python -m srf.ops.common.budget check")
    ```

  - **Three sub-Packages composed with `Conditional`, `Sequential`, `Loop`:**
    - `mutate_pkg = Package("gepa-mutate")` — `select_parent` → `build_reflective_prompt` → `generate_code` (LLMNode). Imports: `from factory.workflow.primitives import Edge, FnNode, LLMNode, Workflow` and `from factory.workflow.package import Package, Port, StateContract, OptKnob`
    - `merge_pkg = Package("gepa-merge")` — `find_merge_candidates` → `build_merge_prompt` → `generate_merge` (LLMNode)
    - `eval_pkg = Package("gepa-eval")` — `sandbox_eval` → `accept_or_reject`
    - `action_pkg = Conditional(gate=merge_gate, branches={"PROCEED": mutate_pkg, "RELOOP": merge_pkg}, name="gepa-action")`
    - `iteration = Sequential(action_pkg, eval_pkg, name="gepa-iteration")`
    - `gepa_mode = Loop(body=iteration, gate=budget_gate, max_iterations=500, name="gepa")`

  - **Exact 5 OptKnobs (from design spec, NOT simplified):**

    | Knob | Kind | Default | Bounds | Node ID | What it controls |
    |------|------|---------|--------|---------|------------------|
    | `temperature` | threshold | 0.7 | [0.3, 0.5, 0.7, 0.9, 1.0] | generate_code | LLM sampling temperature |
    | `parent_selection` | prompt | "best" | ["best", "pareto", "epsilon_greedy"] | select_parent | How parents are chosen for mutation |
    | `max_rejection_context` | threshold | 5.0 | [3.0, 5.0, 8.0, 12.0] | build_reflective_prompt | Rejected attempts shown in reflective prompt |
    | `merge_stagnation_threshold` | threshold | 15.0 | [5.0, 10.0, 15.0, 20.0, 30.0] | find_merge_candidates | Iterations without improvement before merge triggers |
    | `acceptance_mode` | prompt | "strict" | ["strict", "lenient", "off"] | accept_or_reject | How strict the acceptance gate is |

  - **MemoryDeclarations (from design spec):**
    ```python
    memory = [
        MemoryDeclaration(namespace="gepa.population", kind="kv", retention="run"),
        MemoryDeclaration(namespace="gepa.genealogy", kind="graph", retention="run"),
        MemoryDeclaration(namespace="gepa.rejections", kind="log", retention="run"),
    ]
    ```

  - **All 8 ops callables in `srf/ops/gepa/`:**
    - `srf/ops/gepa/population.py` — `select_parent`: reads `population.json`, applies selection strategy (best / pareto / epsilon-greedy per OptKnob), writes `selected_parent.json` with code + score + metrics
    - `srf/ops/gepa/prompts.py`:
      - `build_reflective_prompt`: composes prompt with parent code, eval metrics, last K accepted solutions, last N rejected attempts (code + scores + deltas + errors), failure pattern analysis. Writes `mutate_prompt.md`
      - `build_merge_prompt`: shows 2-3 programs with scores, asks LLM to combine strengths. Writes `merge_prompt.md`
    - `srf/ops/gepa/merge.py` — `find_triplet_or_top2`: searches genealogy graph for valid (i, j, ancestor) triplet, falls back to top-2 by score, deduplicates past attempts. Writes `merge_candidates.json`
    - `srf/ops/gepa/decision.py` — `should_merge`: returns PROCEED (mutate) or RELOOP (merge) based on: `use_merge AND (merge_due OR stagnation >= threshold) AND attempts < max AND pop >= 2`
    - `srf/ops/gepa/acceptance.py` — `accept_or_reject`: compares child score to parent. Strict mode: child > parent for mutate, child >= best_parent for merge. Updates population/genealogy/rejection_history/accepted_history/stagnation counters. Writes `best_solution.py` when new best found
    - `srf/ops/gepa/state.py` — `GEPAState` Pydantic model for `gepa_state.json` (stagnation counter, merge state, iteration count, budget consumed)
  - **FnNode reads/writes match design spec exactly:**
    - `select_parent`: reads `{population.json, gepa_state.json}`, writes `{selected_parent.json}`
    - `build_reflective_prompt`: reads `{selected_parent.json, rejection_history.json, accepted_history.json, task.yaml}`, writes `{mutate_prompt.md}`
    - `generate_code` (LLMNode): reads `{mutate_prompt.md}`, writes `{candidate.py}`
    - `find_merge_candidates`: reads `{population.json, genealogy.json}`, writes `{merge_candidates.json}`
    - `build_merge_prompt`: reads `{merge_candidates.json, task.yaml}`, writes `{merge_prompt.md}`
    - `generate_merge` (LLMNode): reads `{merge_prompt.md}`, writes `{candidate.py}`
    - `sandbox_eval`: reads `{candidate.py, task.yaml}`, writes `{eval_result.json}`
    - `accept_or_reject`: reads `{eval_result.json, candidate.py, selected_parent.json, population.json, genealogy.json, gepa_state.json}`, writes `{population.json, genealogy.json, rejection_history.json, accepted_history.json, gepa_state.json, best_solution.py}`
  - **LLMNode system prompts (from design spec):**
    - `generate_code`: "You are GEPA, a code evolution agent. Given a parent program, evaluation feedback, and a history of rejected attempts, produce an improved version. Output a single fenced code block."
    - `generate_merge`: "You are GEPA merge agent. Given two or three programs with their scores, combine their strengths into a single improved program. Output a single fenced code block."
  - **StateContracts per sub-Package:**
    - mutate_pkg: requires=`{"population.json", "task.yaml"}`, produces=`{"candidate.py"}`
    - merge_pkg: requires=`{"population.json", "genealogy.json", "task.yaml"}`, produces=`{"candidate.py"}`
    - eval_pkg: requires=`{"candidate.py", "task.yaml"}`, produces=`{"eval_result.json", "best_solution.py"}`
  - **Port interfaces per sub-Package:**
    - mutate_pkg: inputs=`[Port("population", "population.json")]`, outputs=`[Port("candidate", "candidate.py")]`
    - merge_pkg: inputs=`[Port("population", "population.json")]`, outputs=`[Port("candidate", "candidate.py")]`
    - eval_pkg: inputs=`[Port("candidate", "candidate.py")]`, outputs=`[Port("result", "eval_result.json")]`
  - Create `tests/test_gepa_mode.py`:
    - Graph validation: all FnNode `callable_name` paths resolve to importable functions
    - Compile round-trip: Package serializes to dict and deserializes back identically
    - OptKnob mutation: changing any of the 5 knobs produces a valid Package
    - StateContract: requires/produces match actual file I/O in each sub-Package
    - Verify Conditional branches map correctly (PROCEED→mutate, RELOOP→merge)
    - Verify Loop max_iterations=500 and budget_gate wiring
  - Create `tests/test_gepa_ops.py` — unit tests for each of the 8 domain callables:
    - `select_parent` with each strategy (best, pareto, epsilon_greedy)
    - `build_reflective_prompt` with varying rejection history lengths
    - `find_triplet_or_top2` with and without valid triplets
    - `should_merge` decision logic for all branch conditions
    - `accept_or_reject` with strict/lenient/off modes
- **Why:** GEPA is the reference implementation — the design spec defines the EXACT Package composition with `Conditional(merge_gate, {mutate, merge})` inside `Loop(budget)`. The 5 OptKnobs (temperature, parent_selection, max_rejection_context, merge_stagnation_threshold, acceptance_mode) are from the spec, not simplified. The ops callables use exact `callable_name` paths from the spec. The MemoryDeclarations define GEPA's runtime state contract. Behavioral fidelity requires matching Flora's implementation at the algorithm level: the reflective prompt, genealogy-based merge candidate selection, and stagnation-gated merge/mutate Conditional are all critical to reproducing Flora's results (Pitfall 1.1).
- **Expected impact:** capability_surface +0.5 (first mode fully operational with composition primitives: Conditional, Sequential, Loop), syntax_check maintained at 1.0, observability maintained at 0.7
- **Priority:** high

### Phase 3: Benchmark tasks + e2e testing + trace validation

#### H3: Port 3 validation tasks and validate GEPA with trace-level fidelity checks

- **Category:** EXPLORE
- **Growth dimension:** capability_surface
- **Backlog item:** SRF scientific research factory - 13 harnesses as composable factory Packages
- **What:**
  - Create `srf/tasks/math/circle_packing/`:
    - `task.yaml`:
      ```yaml
      name: circle_packing
      category: math
      description: "Pack N circles of varying radii into a unit square..."
      initial_code: |
        def solve(n: int, radii: list[float]) -> list[tuple[float, float]]:
            return [(0.5, 0.5)] * n  # trivial baseline
      eval_command: "python eval.py"
      metric: score
      maximize: true
      ```
    - `eval.py` — validates no overlaps (pairwise distance > r_i + r_j), no boundary violations (all circles within [0,1]^2), computes sum of radii. Returns `{"score": float, "metrics": {"coverage": float, "overlaps": int}}`. Fast path: geometry check (<1s)
    - `initial.py` — seed solution: simple greedy packing placing circles by decreasing radius
    - Reference score: 2.634 (OpenEvolve SOTA for n=26)
  - Create `srf/tasks/math/autocorrelation_inequality/`:
    - `task.yaml` — find tight bounds for autocorrelation inequalities. Eval criteria: mathematical correctness + tightness
    - `eval.py` — numerical verification of inequality over random test vectors, symbolic check if scipy available
    - `initial.py` — seed: naive bound from Cauchy-Schwarz
  - Create `srf/tasks/gpu/trimul/`:
    - `task.yaml` — optimize matrix triple multiplication algorithm. Eval criteria: correctness + efficiency (FLOPs or wall time)
    - `eval.py` — correctness check against numpy reference, timing measurement
    - `initial.py` — seed: naive O(n^3) triple product
  - Create `srf/ops/common/trace_validator.py` — trace-level fidelity checker:
    - Parses `trace.jsonl` from SRF and Flora's baseline trace
    - Diffs population evolution sequences (population sizes, elite scores per iteration)
    - Diffs selection events (parent IDs, selection method, tournament outcomes)
    - Diffs merge/mutate Conditional branch decisions (when merge triggered, stagnation counts)
    - Reports behavioral parity score (% of trace events matching within tolerance)
    - Flags anomalies: sudden score jumps (>2 sigma), identical outputs across inputs
  - Create `srf/ops/common/benchmark_compare.py` — comparison report generator:
    - Loads SRF trace and Flora baseline trace for same task
    - Score parity: `srf_score / flora_score >= 0.95` (success criterion from factory.md)
    - Cost parity: `srf_tokens / flora_tokens <= 1.5` (acceptable overhead per Pitfall 1.2: "1.3x overhead acceptable")
    - Behavioral fidelity: trace validator parity score
    - Outputs JSON + human-readable markdown comparison report
  - Update CLI: `srf validate --mode gepa --task circle_packing --baseline-trace path/to/flora_trace.jsonl`
  - Create `tests/test_tasks.py`:
    - Each `task.yaml` loads and validates against schema
    - Each `eval.py` runs on `initial.py` and returns a valid score
    - Each `eval.py` returns score=0 for trivially wrong solutions
    - Task directory convention enforced (category/name/files)
  - Create `tests/test_gepa_e2e.py` — end-to-end test:
    - Run GEPA on circle_packing with mock LLM responses (deterministic, no API calls)
    - Validate Package executes without errors through the full Loop
    - Validate Conditional branches correctly (merge vs mutate based on GateNode)
    - Validate `trace.jsonl` written with correct schema matching Flora's 5-file format
    - Validate `best_solution.py` written and passes `eval.py`
    - Validate budget tracker records token counts from mock responses
    - Validate output directory structure: `outputs/{run_id}/`
  - Create `tests/test_trace_validator.py` — validate trace diffing on synthetic traces with known differences
- **Why:** These 3 tasks are the acceptance test for Phase 1 (factory.md success criterion: "GEPA mode achieves >= 95% of Flora's GEPA scores on the 3 validation tasks with comparable LLM cost"). Trace-level validation is a CEO constraint — score parity alone is insufficient (Pitfall 1.1: "porting may silently break algorithmic behavior"). BenchBench research (2026) confirmed "benchmark porting pipelines typically lack closed-loop validation of discriminative power and behavioral biases." The trace validator specifically checks that GEPA's Conditional merge/mutate branching, genealogy-based triplet selection, and stagnation-gated decisions match Flora's patterns.
- **Expected impact:** capability_surface +0.3 (benchmark tasks + validation infrastructure), observability +0.1 (trace analysis), factory_effectiveness +0.2 (automated fidelity checking)
- **Priority:** high

### Anti-patterns to Avoid

- **Deviating from the design spec's Package structure**: The GEPA workflow graph is `Loop(Sequential(Conditional(merge_gate, {mutate_pkg, merge_pkg}), eval_pkg), budget_gate)`. Do NOT simplify this to a flat FnNode sequence or remove the `Conditional` branching. The composition primitives (`Conditional`, `Sequential`, `Loop`) are the point.
- **Substituting OptKnobs**: The spec defines exactly 5 OptKnobs (temperature, parent_selection, max_rejection_context, merge_stagnation_threshold, acceptance_mode). Do NOT replace these with simpler knobs like population_size or num_iterations. The outer loop evolves THESE 5 knobs.
- **Wrong callable_name paths**: Each FnNode must use the exact `callable_name` from the spec (e.g., `srf.ops.gepa.population:select_parent`, NOT `srf.ops.gepa.select_parents`). The colon-separated `module:function` format is a factory convention.
- **Missing MemoryDeclarations**: The 3 memory namespaces (gepa.population, gepa.genealogy, gepa.rejections) are required for the factory's memory system. Don't skip them.
- **Client-side token estimates for budget tracking**: Always ingest API-returned `usage.input_tokens` / `usage.output_tokens`. Never use tiktoken or string-length for billing (Pitfall 4.1).
- **Implementing modes beyond GEPA**: This session covers ONLY Phase 1-3. Do NOT implement OpenEvolve, AIDE, AI Scientist V2, or any other mode. The architecture supports adding them later via the mode registry and shared ops in `srf/ops/common/`.
- **Pure-Python sandboxes**: Never rely on import filtering alone. Always use Firejail or equivalent. Python's `object.__subclasses__()` bypasses import restrictions (Pitfall 3.1).
- **Skipping trace-level validation**: Score parity (>= 95%) is necessary but not sufficient. Behavioral fidelity (merge/mutate Conditional branching, genealogy-based selection, stagnation thresholds) must match Flora's baselines (Pitfall 1.1, CEO constraint).

### Open Questions

- **Flora's baseline traces**: Where are Flora Jia's original GEPA trace logs? The builder needs exact traces for behavioral fidelity validation. If unavailable, we need to run Flora's GEPA first to produce reference traces.
- **remote-factory Package API**: The builder needs to verify exact import paths (`factory.workflow.primitives`, `factory.workflow.package`) and that `FnNode.callable_name` resolution works for external packages. The design spec notes a bug: `Conditional` doesn't propagate `knobs` or `memory` from child packages — this may need a fix in remote-factory before GEPA works end-to-end.
- **Firejail availability**: The sandbox assumes `firejail` is installed. If unavailable, fall back to `subprocess.run` with `resource` module limits (weaker isolation, adequate for controlled benchmarks).

## Deferred

- **Remaining 12 modes**: OpenEvolve, AIDE, AI Scientist V2, Best-of-N, AutoResearch, AutoResearch Karpathy, AutoScientists, AdaEvolve, EvoX Meta, SCS, ShinkaEvolve, The AI Scientist — all deferred to future sessions. Architecture supports them via mode registry and shared ops.
- **Lab Director**: Multi-mode orchestration agent deferred to future session. Seams designed in Phase 1 (ModeResult protocol, LabDirectorProtocol, uniform Port interface).
- **gVisor/Firecracker migration**: Phase 1 uses Firejail. Upgrade to gVisor/Firecracker when deploying for production untrusted code.
- **OpenTelemetry OTLP export**: Phase 1 uses structlog file output. OTLP export to Jaeger/Tempo deferred until observability infrastructure is provisioned.
- **MAP-Elites outer loop**: Full evolutionary harness selection deferred beyond Lab Director.
