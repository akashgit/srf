# Graph Context — SRF (Scientific Research Factory)

**Generated**: 2026-08-29  
**Graph built at commit**: c45c887 (Initial commit)

## Project Overview

**SRF (Scientific Research Factory)** is a scientific research factory that reimplements 13 AI-driven scientific discovery harnesses (from Flora Jia's harness-comparison benchmark) as composable factory workflow Packages on top of remote-factory's Package ecosystem. A single research question can be refracted through multiple strategies, each with tunable OptKnobs that the outer loop evolves.

**Target**: SRF scientific research factory - 13 harnesses as composable factory Packages (TARGETED MODE - single-item focus)

## Graph Availability

✅ Graph file exists at `graph.json` (166 lines, 8 nodes, 6 edges)  
📊 Current graph is minimal — represents project scaffolding phase, not full implementation  
🎯 Focus context: "SRF scientific research factory harnesses Packages" (from observations.md)

## Current Graph State

The knowledge graph currently captures the **evaluation infrastructure** and **verification hooks** from the initial project setup:

### Nodes Inventory (8 total)

| Node | Type | Location | Community | Purpose |
|------|------|----------|-----------|---------|
| `score.py` | file | eval/score.py:L1 | 0 | Eval script entry point |
| `eval_syntax_check()` | function | eval/score.py:L18 | 2 | Syntax validation eval dimension |
| `eval_observability()` | function | eval/score.py:L53 | 1 | Observability coverage analysis |
| `main()` | function | eval/score.py:L130 | 0 | Eval orchestrator |
| `verify-design.sh` | file | .factory/hooks/verify-design.sh:L1 | 3 | Design verification hook |
| `verify-design.sh script` | entrypoint | .factory/hooks/verify-design.sh:L1 | 3 | Hook execution entry |
| Rationale nodes (×2) | documentation | eval/score.py:L19, L54 | 1, 2 | Design rationale for eval functions |

### Edge Inventory (6 total)

**Eval orchestration flow:**
- `score.py` → `eval_syntax_check()` (indirect_call, inferred, L127)
- `score.py` → `eval_observability()` (indirect_call, inferred, L127)
- `score.py` → `main()` (contains, extracted, L130)

**Design rationale links:**
- Rationale "Verify code has no syntax errors" → `eval_syntax_check()` (rationale_for)
- Rationale "Analyze observability coverage..." → `eval_observability()` (rationale_for)

**Hook structure:**
- `verify-design.sh` → `verify-design.sh script` (contains)

### Communities Detected (4)

| Community | Members | Role |
|-----------|---------|------|
| 0 | score.py, main() | Eval orchestration |
| 1 | eval_observability(), observability rationale | Observability dimension |
| 2 | eval_syntax_check(), syntax rationale | Syntax dimension |
| 3 | verify-design.sh (file + script) | Verification hooks |

## Architectural Layers (Expected vs. Current)

**From factory.md — planned architecture:**

| Layer | Location | Purpose | Current State |
|-------|----------|---------|---------------|
| **Modes** | `srf/modes/` | One `.py` per harness — each builds a Package from factory primitives | 🔴 Not yet implemented |
| **Ops** | `srf/ops/` | Python callables for FnNode.callable_name — domain logic | 🔴 Not yet implemented |
| **Tasks** | `srf/tasks/` | Task definitions with task.yaml + eval.py — benchmark problems | 🔴 Not yet implemented |
| **Lab** | `srf/lab/` | Phase 2 — Lab Director agent for multi-mode orchestration | 🔴 Not yet implemented |
| **Eval** | `eval/` | Evaluation harness (syntax, observability) | ✅ **Current graph focus** |
| **Skills** | `skills/` | Workflow skills for factory modes | ✅ Present (14 workflow skills) |

## Key Modules and Relationships

### 1. Eval Infrastructure (`eval/score.py`)

**Role**: Auto-generated eval script that runs each eval dimension and outputs JSON.

**Structure**:
```
score.py (community 0)
  ├── main() → orchestrates eval execution
  ├── eval_syntax_check() (community 2) → validates syntax (weight 0.833)
  └── eval_observability() (community 1) → analyzes logging coverage (weight 0.167)
```

**Eval dimensions** (from graph + factory.md):
| Dimension | Weight | Parser | Description |
|-----------|--------|--------|-------------|
| syntax_check | 0.833 | exit_code | Verify code has no syntax errors |
| observability | 0.167 | json | Analyze logging coverage, structured logging, request tracing |

**Threshold**: 0.6 (from factory.md)

**Dependencies**:
- Uses subprocess for syntax checks
- Uses ast + regex for observability analysis
- Skips directories: tests, .venv, node_modules, .factory, etc.

### 2. Workflow Skills (`skills/workflow-*`)

**Role**: Pre-built workflow skill definitions for factory modes.

**Inventory** (14 skills):
1. `workflow-create` — meta-mode for creating new factory modes
2. `workflow-design` — interactive design mode with user approval gate
3. `workflow-devopsgym` — devopsgym benchmark workflow
4. `workflow-featurebench` — featurebench workflow
5. `workflow-legacybench` — legacybench workflow
6. `workflow-mini-swebench` — mini SWE-bench workflow
7. `workflow-outer-loop` — evolutionary search for workflow DAGs
8. `workflow-programbench` — programbench workflow
9. `workflow-salitrap` — salitrap workflow
10. `workflow-spec-generate` — spec generation workflow
11. `workflow-swebench` — full SWE-bench benchmark mode
12. `workflow-swebenchifyhard` — swebenchify-hard workflow
13. `workflow-terminalbench` — terminalbench workflow
14. `workflow-tomswe` — tomswe workflow

**Pattern**: Each skill has:
- `SKILL.md` with frontmatter (name, description, argument-hint)
- Multi-phase DAG with gates, CEO reviews, agent dispatch
- Artifact verification steps
- Barrier synchronization for parallel agents

**Example flow** (from workflow-design):
```
discover → graph_update → observe → researcher (×3 parallel) → strategist → builder → QA (×3 parallel)
         ↑                                                      ↑
         └─── automated gates ──────────────────────┘
         └─── user approval gate (steering point) ──┘
```

### 3. Verification Hooks (`.factory/hooks/`)

**Role**: Pre-commit and workflow verification gates.

**Current**: `verify-design.sh` (community 3)
- Triggered during workflow execution
- Validates artifact existence and correctness
- Logs to `.factory/hooks/hook-log.txt`

## Dependency Paths

### Eval Execution Path
```
CLI invocation
  ↓
main() [eval/score.py:L130]
  ↓
EVALS list iteration [L127]
  ├─→ eval_syntax_check() [L18] → subprocess.run(['true'])
  └─→ eval_observability() [L53] → ast.parse + regex scanning
  ↓
JSON output to stdout
```

### Workflow Design Path (from skill DAG)
```
User request
  ↓
workflow-design skill
  ├─→ discover (if .factory/config.json missing)
  ├─→ graph_update
  ├─→ study
  ├─→ researcher (3 parallel: similar, techstack, pitfalls)
  ├─→ strategist
  ├─→ [USER APPROVAL GATE] ← steering point
  ├─→ builder
  └─→ QA (3 parallel: health_checker, code_reviewer, adversarial_tester)
```

## Entry Points and Hotspots

### Entry Points

1. **Eval harness**: `python eval/score.py`
   - Called by: `factory precheck`, `factory finalize`, builder agents
   - Outputs: JSON to stdout with {"results": [...]}

2. **Workflow skills**: Invoked via `factory workflow run <skill-name> <project>`
   - Dispatch agents with `factory agent <role> --task "..." --project <path>`
   - Execute bash gates and verification steps

3. **Smoke test**: `python -c "import srf; print('SRF imported successfully')"`
   - Currently will fail (srf/ module not yet implemented)

### Hotspots (based on frequency of use)

1. **eval/score.py** — executed every experiment cycle
2. **workflow-design** — primary mode for interactive building
3. **workflow-outer-loop** — evolutionary search for mode optimization
4. **workflow-create** — meta-mode for creating new harnesses

## Missing Structure (Not Yet in Graph)

The following are **specified in factory.md** but not yet implemented (hence not in graph):

### Phase 1 Scaffolding (GEPA mode)
- `srf/__init__.py` — package entry point
- `srf/modes/gepa.py` — GEPA harness Package definition
- `srf/ops/*.py` — domain callables (code parsing, eval sandbox, budget tracking)
- `srf/tasks/circle_packing/` — benchmark task 1
- `srf/tasks/autocorrelation_inequality/` — benchmark task 2
- `srf/tasks/trimul/` — benchmark task 3
- `tests/test_gepa.py` — GEPA validation tests
- `pyproject.toml` — dependencies and CLI entry points

### Phase 2 Modes (priority order)
1. OpenEvolve
2. AIDE
3. AI Scientist V2
4. 9 remaining harnesses

### Phase 3 Lab Director
- `srf/lab/director.py` — multi-mode orchestration agent

### Guards (from factory.md)
- All mode Packages must expose uniform interface: `inputs=[Port("task", "task.yaml")]`, `outputs=[Port("best_solution", "best_solution.py"), Port("trace", "trace.jsonl")]`
- Every FnNode callable must be importable via `callable_name` path
- LLMNode model references must use factory-supported names (sonnet, opus, haiku)
- OptKnob bounds must be non-empty lists with default value included
- StateContract.requires and .produces must accurately reflect file I/O

## Observability Coverage (from observations.md)

**Current state**: 0.0% (0/0 functions have logging)
- No source files found to analyze (srf/ not yet created)
- No structured logging detected
- No request tracing detected

**Recommendation**: Phase 1 should include structured logging from the start (structlog or similar).

## Implementation Roadmap

**Phase 1: Scaffolding + GEPA** (current focus)
1. ✅ Repo scaffolding — factory.md created, eval/score.py exists
2. 🔴 Common infrastructure — eval sandbox, budget tracking, tracing, code parsing
3. 🔴 GEPA mode — Package definition + all domain callables
4. 🔴 Port 3 benchmark tasks — circle_packing, autocorrelation_inequality, trimul
5. 🔴 Test GEPA — graph validation, compile round-trip, knob mutation, e2e
6. 🔴 Validate — run GEPA on ported tasks, compare to Flora's baselines

**Success criterion**: GEPA mode achieves ≥95% of Flora's GEPA scores on the 3 validation tasks with comparable LLM cost.

## Graph Growth Prediction

As Phase 1 implementation progresses, the graph will grow to include:

**Expected nodes** (~50-100):
- `srf/__init__.py` + submodules
- Mode Packages: `gepa.py`, `open_evolve.py`, `aide.py`, etc.
- Ops callables: `parse_code()`, `run_eval()`, `track_budget()`, etc.
- Task definitions: `task.yaml` parsers, `eval.py` evaluators
- Test suite: `test_gepa.py`, `test_modes.py`, etc.

**Expected communities** (4-6):
- Community 0: Eval orchestration (already exists)
- Community 1: Mode Packages (gepa, open_evolve, etc.)
- Community 2: Ops layer (domain callables)
- Community 3: Task infrastructure (task.yaml, eval.py)
- Community 4: Test suite
- Community 5: Lab Director (Phase 3)

**Expected hotspots**:
- `srf/modes/gepa.py` — first mode, reference implementation
- `srf/ops/eval_sandbox.py` — shared by all modes
- `srf/tasks/*/eval.py` — executed every experiment run

## Next Steps for Graph Exploration

Once Phase 1 implementation begins:

1. **Re-run graph update**: `factory graph update $PROJECT_PATH`
2. **Query for GEPA mode**: `factory graph query "$PROJECT_PATH" "gepa mode package" --depth 2`
3. **Trace dependency paths**: `factory graph path "$PROJECT_PATH" "gepa.py" "eval_sandbox.py"`
4. **Analyze communities**: Check if modes, ops, and tasks form distinct communities
5. **Identify hotspots**: Use degree centrality to find most-connected callables

## References

- **factory.md**: Project configuration and implementation phases
- **observations.md**: Study context and backlog (TARGETED MODE — single-item focus)
- **graph.json**: Knowledge graph (8 nodes, 6 edges, 4 communities)
- **skills/workflow-design/SKILL.md**: Interactive design workflow DAG
- **eval/score.py**: Evaluation harness implementation

---

**Status**: Graph reflects initial scaffolding only. Phase 1 implementation will add ~50-100 nodes for GEPA mode, ops callables, and benchmark tasks. Current graph is foundation for eval infrastructure and workflow orchestration.
