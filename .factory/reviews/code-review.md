# Code Review — PR #21: SRF Scaffold, GEPA Mode, Benchmark Tasks

**Reviewer:** code_reviewer agent
**Timestamp:** 2026-08-29T20:15:00Z
**Files reviewed:** 44 changed files
**Lines added:** ~3,459

---

## Overall Result: ISSUES_FOUND

**Spec Fidelity:** 8/10 acceptance criteria met (2 deviations noted)

---

## 1. Correctness — FAIL

### Issue C1: Merge path does not write `selected_parent.json` (important)
- **File:** `srf/ops/gepa/merge.py` / `srf/ops/gepa/acceptance.py:34`
- **Evidence:** When the Conditional takes the RELOOP (merge) branch, `find_triplet_or_top2` writes `merge_candidates.json` but does NOT write `selected_parent.json`. However, `accept_or_reject` (which runs after both branches via the Sequential) reads `selected_parent.json` at line 34 to get the parent score and ID for comparison. After a merge, this file contains stale data from the previous mutation iteration.
- **Impact:** The parent_id and parent_score used for acceptance/rejection after a merge will be from the previous mutate cycle, not from the merge candidates. Genealogy edges will be wrong. Score comparison may accept/reject incorrectly.
- **Severity:** important

### Issue C2: `merge_attempts` counter never incremented (important)
- **File:** `srf/ops/gepa/decision.py:56` / `srf/ops/gepa/acceptance.py`
- **Evidence:** `_decide()` checks `state.merge_attempts >= max_merge_attempts` (line 56 in decision.py) and resets it to 0 on new best (acceptance.py:97). But no code ever increments `state.merge_attempts`. The exhaustion guard at decision.py:56 will never trigger.
- **Impact:** If merge keeps failing, the system will keep retrying merge indefinitely instead of falling back to mutation after 5 attempts.
- **Severity:** important

### Issue C3: Candidate source always logged as "mutation" (minor)
- **File:** `srf/ops/gepa/acceptance.py:50`
- **Evidence:** `log_candidate(ctx, child_id, parent_id, "mutation", ...)` — the source parameter is hardcoded as `"mutation"` regardless of whether the candidate came from a merge. The trace validator uses this field for behavioral fidelity checking.
- **Impact:** Trace analysis will show 100% mutation rate even when merges occurred, undermining behavioral fidelity validation.
- **Severity:** minor (tracing accuracy, not runtime)

### Issue C4: Acceptance logic doesn't distinguish merge vs mutate (important)
- **File:** `srf/ops/gepa/acceptance.py:115-120`
- **Evidence:** The design spec states: "Strict mode: child > parent for mutate, child >= best_parent for merge." The implementation at `_check_acceptance` uses `child_score > parent_score` for both. No merge-specific acceptance path exists.
- **Severity:** important (spec deviation, may affect behavioral parity with Flora)

### All 8 ops callables are implemented and non-stubbed:
- `select_parent` — correct selection logic for all 3 strategies ✓
- `build_reflective_prompt` — correctly uses max_rejection_context knob ✓
- `build_merge_prompt` — correctly formats 2-3 candidates ✓
- `find_triplet_or_top2` — correct genealogy traversal with top-2 fallback ✓
- `should_merge` — correct decision logic (except merge_attempts tracking) ✓
- `accept_or_reject` — correct acceptance flow (except merge/mutate distinction) ✓
- `run_eval` — correct sandbox execution and JSON parsing ✓
- `check_budget` — correct budget gate with RELOOP/PROCEED ✓

---

## 2. Security — PASS

- No hardcoded secrets, API keys, or passwords in the repo ✓
- API key read from environment variable `ANTHROPIC_API_KEY` (correct pattern) ✓
- Firejail sandbox uses `--net=none`, seccomp, rlimits, private mount ✓
- No SQL, XSS, or command injection vectors ✓
- subprocess calls use list form (no shell=True) ✓
- Gate evaluator commands are from hardcoded workflow definition, not user input ✓

### Issue S1: Subprocess fallback lacks resource limits (minor)
- **File:** `srf/ops/common/sandbox.py:108-110`
- **Evidence:** The design spec calls for `resource` module limits (memory, nproc) in the subprocess fallback when Firejail is unavailable. `_run_subprocess` only has a timeout — no memory, file size, or process count limits.
- **Impact:** Without Firejail, candidate code could consume unlimited memory or spawn processes. Mitigated by: (a) this is the fallback path, (b) candidate code is LLM-generated for benchmark tasks, not adversarial.
- **Severity:** minor (adequate for Phase 1 controlled benchmarks per spec: "adequate for controlled benchmark tasks")

---

## 3. Edge Cases — PASS

- Empty population handled: `select_parent` falls back to seed solution ✓
- Missing `candidate.py` handled: `run_eval` returns error result ✓
- Budget at zero: `init_budget` sets correct limit from ctx ✓
- No JSON output from eval: `_parse_eval_output` returns error ✓
- Timeout in sandbox: caught by `subprocess.TimeoutExpired` ✓
- Empty trace files: `validate_traces` handles empty/missing files ✓
- Population < 2 for merge: `should_merge` returns PROCEED ✓

### Issue E1: `_parse_yaml` does not handle list values in task.yaml (minor)
- **File:** `srf/tasks/registry.py:30-63`
- **Evidence:** The custom YAML parser handles scalars and multiline strings but not YAML lists. If a future task.yaml uses list values (e.g., `tags: [math, optimization]`), they'll be parsed as raw strings. Not triggered by current task.yaml files.
- **Severity:** minor (no current impact, all 3 task.yaml files use only scalars and multiline)

---

## 4. Missing Tests — FAIL

### Issue T1: No test for merge-triggered E2E path (important)
- **File:** `tests/test_gepa_e2e.py`
- **Evidence:** The E2E test uses `--budget 3` with default `merge_stagnation_threshold=15`. Merge will never trigger within 3 iterations. No test verifies the Conditional → RELOOP → merge_pkg path end-to-end.
- **Severity:** important

### Issue T2: No test for `accept_or_reject` error path (minor)
- **File:** `tests/test_gepa_ops.py`
- **Evidence:** Tests cover accept-improvement, reject-worse, lenient-accept. No test for `child_error` truthy (early return path at acceptance.py:58-62).
- **Severity:** minor

### Issue T3: No test for `epsilon_greedy` strategy (minor)
- **File:** `tests/test_gepa_ops.py`
- **Evidence:** TestSelectParent covers `best` and `pareto` but not `epsilon_greedy`. The epsilon_greedy path (population.py:59-61) with its random.random() < 0.1 branch is untested.
- **Severity:** minor

### Tests that DO exist (50 tests claimed passing):
- Sandbox: parse output, missing candidate, simple eval ✓
- GEPA mode: workflow structure, branches, FnNode resolution, knobs, memory, contracts, gates ✓
- GEPA ops: select_parent (best/pareto), reflective prompt, merge prompt, merge candidates (top2/insufficient), should_merge (5 cases), accept/reject (strict/lenient) ✓
- Tasks: discovery, schema, category filter, YAML parsing, eval-on-initial for all 3 tasks ✓
- E2E: full CLI pipeline, modes/tasks commands, unknown mode/task errors, knob overrides ✓
- Trace validator: single trace, two traces, anomaly detection ✓

---

## 5. Style & Consistency — PASS

### Issue Y1: `import os` placed after its usage in `budget.py` (minor)
- **File:** `srf/ops/common/budget.py:79`
- **Evidence:** `os.environ` is used at line 64 in `check()`, but `import os` appears at line 79 (module level, after the function definition). This works because module-level statements execute at import time before any function call, but it violates PEP 8 and is confusing to read.
- **Severity:** minor

### Issue Y2: File handle not tracked in logging config (minor)
- **File:** `srf/logging/config.py:30`
- **Evidence:** `open(log_file, "a")` is passed directly to `WriteLoggerFactory` without being stored in a variable. The handle can't be explicitly closed on shutdown. Standard practice for logging in long-running processes but worth noting.
- **Severity:** minor

### Positives:
- Consistent naming conventions (snake_case everywhere) ✓
- Clean module organization matching the spec layers (modes/ops/tasks) ✓
- No dead code or unused imports ✓
- Proper use of `from __future__ import annotations` ✓
- Consistent use of structlog for all logging ✓
- Pydantic model for GEPAState is clean and well-structured ✓
- All files under 365 lines (max: `_factory_shim.py` at 364) ✓

---

## 6. Scope Compliance — PASS

### What's implemented vs. spec:
- ✅ Phase 1: pyproject.toml, CLI (run/modes/tasks/validate), ModeRegistry, TaskRegistry, sandbox, budget, tracing, code parsing, logging, Lab Director seams
- ✅ Phase 2: GEPA mode with exact DAG structure: `Loop(Sequential(Conditional(merge_gate, {PROCEED→mutate, RELOOP→merge}), eval), budget_gate, max_iterations=500)`
- ✅ Phase 2: All 5 OptKnobs (temperature, parent_selection, max_rejection_context, merge_stagnation_threshold, acceptance_mode) with correct names, kinds, defaults, and bounds
- ✅ Phase 2: All 3 MemoryDeclarations (gepa.population, gepa.genealogy, gepa.rejections)
- ✅ Phase 2: All 8 ops callables with exact `callable_name` paths (verified importable in tests)
- ✅ Phase 2: StateContracts match spec for all 3 sub-packages
- ✅ Phase 2: Port interfaces match spec for all 3 sub-packages
- ✅ Phase 2: LLMNode system prompts match spec text
- ✅ Phase 3: 3 benchmark tasks (circle_packing, autocorrelation_inequality, trimul) with eval.py + initial.py
- ✅ Phase 3: Trace validator with behavioral parity scoring
- ✅ Phase 3: Benchmark comparator with score/cost/behavioral parity
- ✅ Phase 3: All initial.py solutions score > 0 on their eval.py

### Issue SC1: Workflow missing uniform Port interface (minor)
- **File:** `srf/modes/gepa.py:225-233` / `factory.md` guard
- **Evidence:** factory.md guard states: "All mode Packages must expose the uniform interface: inputs=[Port("task", "task.yaml")], outputs=[Port("best_solution", "best_solution.py"), Port("trace", "trace.jsonl")]". The Workflow returned by `build_gepa_workflow()` does not declare these top-level Ports. The sub-packages have their own Ports but not the uniform interface.
- **Impact:** Won't block Phase 1 execution (the shim executor doesn't check Ports), but blocks future Lab Director integration which needs the uniform interface.
- **Severity:** minor (Phase 2 concern)

### No unrelated changes (no scope creep) ✓
### No modes beyond GEPA implemented ✓
### No modifications to off-limits files (.factory/**, factory.md, CLAUDE.md, eval/score.py) ✓

---

## 7. Guardrail Compliance — PASS

- ✅ No file exceeds 500 lines (max: 364 in `_factory_shim.py`)
- ✅ All modified files within declared scope (`srf/**/*.py`, `tests/**/*.py`, `pyproject.toml`, task files)
- ✅ No fixed surfaces modified (eval/score.py, .factory/, factory.md, CLAUDE.md untouched)
- ✅ No secrets or credentials in repo
- ✅ No existing tests deleted or overwritten (greenfield, all tests are new)
- ✅ FnNode callable_name paths all use exact `module:function` format and resolve
- ✅ LLMNode model references use factory-supported names ("sonnet")
- ✅ OptKnob bounds are non-empty lists with defaults included (verified in test)
- ✅ StateContract requires/produces match actual file I/O per op

---

## Plan Completion Status

| Deliverable | Status | Notes |
|------------|--------|-------|
| pyproject.toml | ✅ Complete | Dependencies, CLI entry point, package config |
| srf/__init__.py | ✅ Complete | Version metadata |
| srf/cli.py | ✅ Complete | run/modes/tasks/validate commands |
| srf/registry.py | ✅ Complete | Auto-discovery for modes and tasks |
| srf/_factory_shim.py | ✅ Complete | All primitives + WorkflowExecutor |
| srf/modes/gepa.py | ✅ Complete | Exact DAG from spec, 5 knobs, 3 memory |
| srf/ops/gepa/* (6 files) | ✅ Complete | All 8 callables implemented, non-stubbed |
| srf/ops/common/* (6 files) | ✅ Complete | Sandbox, budget, tracing, code parsing, trace validator, benchmark compare |
| srf/tasks/* (3 tasks) | ✅ Complete | eval.py + initial.py for all 3 |
| srf/logging/config.py | ✅ Complete | structlog JSON config |
| srf/lab/protocol.py | ✅ Complete | Phase 2 seams |
| tests/* (7 files) | ✅ Complete | ~50 tests covering all phases |

**No stubbed deliverables found.** All functions contain real logic, not `pass` or `raise NotImplementedError`.

---

## Issue Summary

| # | Category | Severity | File | Summary |
|---|----------|----------|------|---------|
| C1 | Correctness | important | acceptance.py / merge.py | Merge path doesn't write selected_parent.json — stale parent used for acceptance |
| C2 | Correctness | important | decision.py / acceptance.py | merge_attempts counter never incremented — exhaustion guard dead code |
| C3 | Correctness | minor | acceptance.py:50 | Candidate source always "mutation" even after merge |
| C4 | Correctness | important | acceptance.py:115-120 | No merge-specific acceptance logic (spec: child >= best_parent for merge) |
| S1 | Security | minor | sandbox.py:108-110 | Subprocess fallback missing resource module limits |
| E1 | Edge Cases | minor | registry.py:30-63 | Custom YAML parser doesn't handle list values |
| T1 | Missing Tests | important | test_gepa_e2e.py | No test exercises the merge path end-to-end |
| T2 | Missing Tests | minor | test_gepa_ops.py | No test for accept_or_reject error early-return |
| T3 | Missing Tests | minor | test_gepa_ops.py | No test for epsilon_greedy selection strategy |
| Y1 | Style | minor | budget.py:79 | import os placed after its usage in function |
| Y2 | Style | minor | config.py:30 | File handle not tracked for cleanup |
| SC1 | Scope | minor | gepa.py:225-233 | Workflow missing uniform Port interface from factory.md guard |

**Critical issues: 0**
**Important issues: 4** (C1, C2, C4, T1)
**Minor issues: 8** (C3, S1, E1, T2, T3, Y1, Y2, SC1)

---

## Gate Decision

**ISSUES_FOUND — Proceed to adversarial testing.**

No critical issues found. The 4 important issues (merge path wiring, merge_attempts tracking, merge-specific acceptance, merge E2E test) are all in the merge sub-flow and won't cause runtime crashes on the happy path (mutation-only execution). The E2E test confirms the primary mutation pipeline works correctly end-to-end. The merge path issues should be fixed but do not block adversarial testing.
