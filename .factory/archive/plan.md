---
tags: [factory, strategy, srf, approved]
project: srf
date: 2026-08-29
source: factory-archivist
---

# SRF Build Plan — Approved Strategy Archive

## Vision

SRF (Scientific Research Factory) reimplements 13 AI-driven scientific discovery harnesses from Flora Jia's harness-comparison benchmark as composable factory workflow Packages on top of remote-factory's Package ecosystem. A single research question can be refracted through multiple strategies, each with tunable OptKnobs that the outer loop evolves—making SRF a harness discovery platform, not just a harness collection.

### Strategic Goals

- **Fidelity**: Port GEPA's behavioral algorithm exactly from Flora, validated at the trace level (merge/mutate Conditional branching, genealogy-based triplet selection, stagnation-gated decisions)
- **Composability**: Use remote-factory primitives (`Package`, `Sequential`, `Parallel`, `Conditional`, `Loop`, `FnNode`, `LLMNode`, `GateNode`, `OptKnob`, `Port`, `MemoryDeclaration`, `StateContract`) as the core DAG abstraction
- **Extensibility**: Design architecture to support all 13 modes via mode registry and shared ops, deferring 12 modes to future sessions
- **Observability**: Structured logging (structlog + JSON), Flora-compatible 5-file trace format, budget tracking with API-returned token counts

## 3-Phase Build Scope

### Phase 1: Project Scaffold + Eval Harness
**H1: SRF package scaffold with registry, common ops, eval sandbox, budget tracking, tracing, and Pydantic models**

**Delivers:**
- Python 3.12+ project with `pyproject.toml` (dependencies: `remote-factory`, `structlog`, `pydantic>=2.10`, `httpx[http2]`, `opentelemetry-api`, `opentelemetry-sdk`)
- CLI entry point: `srf = srf.cli:main` supporting:
  - `srf run --mode gepa --task circle_packing --budget 50`
  - `srf run --mode gepa --task circle_packing --knob temperature=0.9 --knob parent_selection=pareto`
  - `srf modes` — list registered modes
  - `srf tasks` / `srf tasks --category math` — list available tasks
- **ModeRegistry**: auto-discovers `srf/modes/*.py`, maps mode names to Package builders
- **TaskRegistry**: discovers tasks by directory convention under `srf/tasks/`
- **Sandbox runner** (`srf/ops/common/sandbox.py`): Firejail-based eval isolation with `--seccomp=socket`, timeout enforcement, resource limits, fallback to `subprocess` + `resource` module
- **Budget tracker** (`srf/ops/common/budget.py`): Tracks LLM cost (from API `usage.input_tokens`/`usage.output_tokens`) and eval count, GateNode callable for reloop/proceed decisions
- **Structured logging** (`srf/logging/config.py`, `srf/ops/common/tracing.py`): structlog JSON renderer, ISO timestamps, Flora-compatible trace format (`evaluations.jsonl`, `candidates.jsonl`, `llm_calls.jsonl`, `policy_decisions.jsonl`, `budget.jsonl`)
- **Support modules**: `code_parsing.py` (fenced code blocks), `MemoryDeclaration` + `StateContract` Pydantic models
- **Tests**: sandbox isolation (`test_common_sandbox.py`), task discovery + schema validation (`test_task_registry.py`)

**Expected Impact:**
- `syntax_check`: 0.0 → 1.0 (valid Python across all files)
- `observability`: 0.0 → 0.7 (structlog in all ops, JSON output, context binding)
- `capability_surface`: +0.3 (core infrastructure operational)

**Priority:** High

---

### Phase 2: GEPA Mode — Faithful Package Implementation
**H2: GEPA mode with exact Package structure, all ops callables, 5 OptKnobs, and MemoryDeclarations**

**Delivers:**
- **GEPA Package** in `srf/modes/gepa.py` matching design spec exactly:
  ```
  Loop(name="gepa", max_iterations=500)
  │
  ├── body = Sequential(name="gepa-iteration")
  │   ├── Conditional(name="gepa-action", gate=merge_decision)
  │   │   ├── PROCEED → Package("gepa-mutate")
  │   │   │   ├── select_parent (FnNode)
  │   │   │   ├── build_reflective_prompt (FnNode)
  │   │   │   └── generate_code (LLMNode)
  │   │   └── RELOOP → Package("gepa-merge")
  │   │       ├── find_merge_candidates (FnNode)
  │   │       ├── build_merge_prompt (FnNode)
  │   │       └── generate_merge (LLMNode)
  │   └── Package("gepa-eval")
  │       ├── sandbox_eval (FnNode)
  │       └── accept_or_reject (FnNode)
  └── gate: budget_check (GateNode)
  ```

- **Exactly 5 OptKnobs** (from design spec, NOT simplified):
  | Knob | Default | Bounds | Controls |
  |------|---------|--------|----------|
  | `temperature` | 0.7 | [0.3, 0.5, 0.7, 0.9, 1.0] | LLM sampling in generate_code |
  | `parent_selection` | "best" | ["best", "pareto", "epsilon_greedy"] | Selection strategy in select_parent |
  | `max_rejection_context` | 5.0 | [3.0, 5.0, 8.0, 12.0] | Rejected attempts in reflective prompt |
  | `merge_stagnation_threshold` | 15.0 | [5.0, 10.0, 15.0, 20.0, 30.0] | Iterations before merge triggers |
  | `acceptance_mode` | "strict" | ["strict", "lenient", "off"] | Strictness of acceptance gate |

- **All 8 ops callables** in `srf/ops/gepa/`:
  - `population.py:select_parent` — reads `population.json`, applies selection strategy per OptKnob
  - `prompts.py:build_reflective_prompt` — composes prompt with parent code, metrics, last K accepted solutions, last N rejected attempts, failure pattern analysis
  - `prompts.py:build_merge_prompt` — shows 2-3 programs, asks to combine strengths
  - `merge.py:find_triplet_or_top2` — genealogy graph triplet search with deduplication, fallback to top-2
  - `decision.py:should_merge` — Conditional evaluator returning PROCEED (mutate) or RELOOP (merge)
  - `acceptance.py:accept_or_reject` — strict/lenient/off modes, population/genealogy updates
  - `state.py:GEPAState` — Pydantic model for `gepa_state.json` (stagnation, merge state, iteration count)
  - `sandbox_eval` + `accept_or_reject` compose the eval Package

- **3 MemoryDeclarations**:
  ```python
  MemoryDeclaration(namespace="gepa.population", kind="kv", retention="run")
  MemoryDeclaration(namespace="gepa.genealogy", kind="graph", retention="run")
  MemoryDeclaration(namespace="gepa.rejections", kind="log", retention="run")
  ```

- **StateContracts per sub-Package**:
  - mutate_pkg: requires `{population.json, task.yaml}` → produces `{candidate.py}`
  - merge_pkg: requires `{population.json, genealogy.json, task.yaml}` → produces `{candidate.py}`
  - eval_pkg: requires `{candidate.py, task.yaml}` → produces `{eval_result.json, best_solution.py}`

- **LLMNode system prompts** (design spec):
  - generate_code: "You are GEPA, a code evolution agent..."
  - generate_merge: "You are GEPA merge agent..."

- **Tests** (`test_gepa_mode.py`, `test_gepa_ops.py`):
  - Graph validation: all `callable_name` paths resolve
  - Compile round-trip: Package serialization/deserialization
  - OptKnob mutation: all 5 knobs produce valid Package
  - StateContract matching
  - Conditional branch routing (PROCEED→mutate, RELOOP→merge)
  - Loop + budget_gate wiring
  - Unit tests for all 8 ops callables with edge cases

**Expected Impact:**
- `capability_surface`: +0.5 (first mode fully operational with composition primitives)
- `syntax_check`: 1.0 (maintained)
- `observability`: 0.7 (maintained)

**Priority:** High

---

### Phase 3: Benchmark Tasks + E2E Testing + Trace Validation
**H3: Port 3 validation tasks and validate GEPA with trace-level fidelity checks**

**Delivers:**
- **3 benchmark tasks** (`srf/tasks/{category}/{task_name}/`):
  - `math/circle_packing`: N circles, varying radii, unit square. Eval: pairwise distance, boundary violation, coverage sum. Reference SOTA: 2.634 (OpenEvolve)
  - `math/autocorrelation_inequality`: Find tight bounds. Eval: correctness + tightness via numerical verification
  - `gpu/trimul`: Matrix triple multiplication optimization. Eval: correctness (vs numpy) + timing

  Each task includes `task.yaml`, `eval.py`, `initial.py` with deterministic scoring and fast validation (<1s)

- **Trace-level validation** (`srf/ops/common/trace_validator.py`):
  - Parses `trace.jsonl` (SRF vs Flora baseline)
  - Diffs population evolution (sizes, elite scores per iteration)
  - Diffs selection events (parent IDs, selection method, tournament outcomes)
  - Diffs Conditional branch decisions (merge vs mutate timing, stagnation counts)
  - Reports behavioral parity score (% of events matching within tolerance)
  - Flags anomalies: sudden score jumps (>2 sigma), identical outputs

- **Comparison report** (`srf/ops/common/benchmark_compare.py`):
  - Score parity: `srf_score / flora_score >= 0.95` (success criterion)
  - Cost parity: `srf_tokens / flora_tokens <= 1.5` (acceptable overhead per Pitfall 1.2)
  - Behavioral fidelity: trace validator parity score
  - JSON + markdown comparison output

- **CLI validation**: `srf validate --mode gepa --task circle_packing --baseline-trace path/to/flora_trace.jsonl`

- **Tests** (`test_tasks.py`, `test_gepa_e2e.py`, `test_trace_validator.py`):
  - Task loading + schema validation
  - `eval.py` runs on `initial.py`, returns valid score
  - E2E GEPA execution with mock LLM (deterministic, no API)
  - Package execution through full Loop
  - Conditional branching correctness
  - Trace format matching Flora's 5-file spec
  - Budget tracker records token counts
  - Output directory structure validation
  - Trace diffing on synthetic traces with known differences

**Expected Impact:**
- `capability_surface`: +0.3 (benchmark tasks + validation infrastructure)
- `observability`: +0.1 (trace analysis)
- `factory_effectiveness`: +0.2 (automated fidelity checking)

**Priority:** High

---

## Key Constraints

### Architectural Constraints
1. **Language/Runtime**: Python 3.12+ — all implementations, ops callables, benchmark tasks
2. **Framework**: remote-factory Package primitives (`factory.workflow.primitives`, `factory.workflow.package`) — NO Prefect, Dagster, or Temporal
3. **Data Storage**: Filesystem-based (`trace.jsonl`, `task.yaml`, `best_solution.py`, `population.json`, `genealogy.json`, `gepa_state.json`) — NO database for Phase 1
4. **Key Libraries**:
   - `remote-factory` — DAG primitives (Sequential, Parallel, Conditional, Loop, FnNode, LLMNode, GateNode)
   - `structlog` — structured JSON logging (80% faster parsing, CNCF standard)
   - `pydantic>=2.10` — Rust-backed validation (5-50x faster than v1)
   - `httpx[http2]` — async LLM client, connection pooling, HTTP/2, vendor lock-in free

### Behavioral Fidelity Constraints
1. **GEPA Package structure MUST match spec** — `Loop(Sequential(Conditional(merge_gate, {mutate_pkg, merge_pkg}), eval_pkg), budget_gate)`. No simplification to flat FnNode sequences. The composition primitives are the point.
2. **5 OptKnobs MUST be exactly** — temperature, parent_selection, max_rejection_context, merge_stagnation_threshold, acceptance_mode. No substitutions with simpler knobs (e.g., population_size).
3. **callable_name paths MUST use exact spec format** — `module:function` (e.g., `srf.ops.gepa.population:select_parent`, NOT `srf.ops.gepa.select_parents`)
4. **3 MemoryDeclarations MUST be included** — gepa.population, gepa.genealogy, gepa.rejections
5. **Budget tracking MUST ingest API-returned token counts** — NEVER use tiktoken or string-length estimates (Pitfall 4.1: "client-side estimates diverge from billing")
6. **Trace-level behavioral validation REQUIRED** — score parity (≥95%) is necessary but insufficient. Merge/mutate Conditional branching, genealogy-based selection, stagnation thresholds must match Flora baselines (Pitfall 1.1, CEO constraint).

### Security Constraints
1. **Sandbox isolation MANDATORY** — Firejail with `--seccomp=socket`, `--rlimit-nproc=32`, `--rlimit-nofile=32`, `--rlimit-as=1096m`, `--net=none`. Fallback to `subprocess` + `resource` module if Firejail unavailable.
2. **Never rely on import filtering alone** — Python's `object.__subclasses__()` bypasses restrictions. Always use OS-level sandbox.

### Wiring Constraint (User Directive)
**Everything must be fully wired end-to-end.** CLI must work as a real user would use it:
- `srf run --mode gepa --task circle_packing --budget 50` must execute the full pipeline: CLI → registry → mode loader → Package execution → ops callables → sandbox → trace output
- No internal test shortcuts — tests must validate actual wiring, not just isolated functions
- E2E validation must run the actual CLI from a clean session, not internal calls

---

## Deferred Items

All items below are explicitly deferred to future sessions. Architecture supports them via mode registry, shared ops, and uniform Port/StateContract interfaces:

### Remaining 12 Harness Modes
1. OpenEvolve
2. AIDE
3. AI Scientist V2
4. Best-of-N
5. AutoResearch
6. AutoResearch Karpathy
7. AutoScientists
8. AdaEvolve
9. EvoX Meta
10. SCS
11. ShinkaEvolve
12. The AI Scientist

### Infrastructure Upgrades
- **Lab Director**: Multi-mode orchestration agent (seams designed in Phase 1: `ModeResult` protocol, `LabDirectorProtocol`, uniform Port interface)
- **gVisor/Firecracker migration**: Upgrade from Firejail when deploying for production untrusted code
- **OpenTelemetry OTLP export**: Replace structlog file output with Jaeger/Tempo when observability infrastructure provisioned
- **MAP-Elites outer loop**: Full evolutionary harness selection (depends on Lab Director)

---

## Open Questions (Pending Resolution)

1. **Flora's baseline traces**: Where are the original GEPA trace logs? Builder needs exact traces for behavioral fidelity validation. If unavailable, Flora's GEPA must run first to produce reference traces.
2. **remote-factory Package API stability**: Verify exact import paths (`factory.workflow.primitives`, `factory.workflow.package`) and `FnNode.callable_name` resolution for external packages. Design spec notes a bug: `Conditional` may not propagate `knobs` or `memory` from child packages — may need upstream fix before GEPA works end-to-end.
3. **Firejail availability**: Sandbox assumes `firejail` is installed. Fallback to `subprocess` + `resource` module is weaker but adequate for controlled benchmarks.

---

## Approval Summary

- **Verdict**: PROCEED (after redirect correction)
- **Approved by**: CEO (after strategist redirect)
- **Date**: 2026-08-29
- **Scope adherence**: Plan matches design spec exactly — GEPA DAG, 5 OptKnobs, 8 ops callables, 3 MemoryDeclarations, deferred 12 modes
- **User directive**: Everything fully wired end-to-end. CLI must work. E2E validation must run actual CLI.

This plan is the authoritative scope for Phase 1–3 build execution.
