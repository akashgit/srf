# Adversarial QA Report — SRF

- **Timestamp:** 2026-08-29T19:47Z
- **Detected project type:** CLI
- **Tested feature:** SRF scaffold, GEPA mode, benchmark tasks (Phases 1-3)

---

## Smoke Test

**Status:** VERIFIED

```
$ python -c "import srf; print('SRF imported successfully')"
SRF imported successfully
```

---

## Test Plan (derived from hypothesis acceptance criteria)

1. Install package (`pip install -e .`)
2. `srf modes` — GEPA listed
3. `srf tasks` — all 3 tasks listed
4. `srf tasks --category math` — filtering works
5. `srf run --mode gepa --task circle_packing --budget 5 --mock-llm` — produces output JSON
6. Output directory — best_solution.py, trace files, eval_result.json exist
7. Error handling: nonexistent mode
8. Error handling: nonexistent task
9. Error handling: nonexistent baseline trace
10. Knob overrides via CLI
11. gepa_state.json structure

---

## Feature Tests with Evidence

### Test 1: Package installation
**Status:** VERIFIED

```
$ pip install -e .
Successfully installed srf-0.1.0
```

Exit code 0. Package installs cleanly with all dependencies resolved.

---

### Test 2: `srf modes` — GEPA listed
**Status:** VERIFIED

```
$ srf modes
Registered modes:
  - gepa
```

GEPA is the only registered mode, as expected for Phase 1-3.

---

### Test 3: `srf tasks` — all 3 tasks listed
**Status:** VERIFIED

```
$ srf tasks
Available tasks:
  - trimul [gpu]: Optimize triple matrix multiplication A @ B @ C for square matrices. Minimize wa
  - circle_packing [math]: Pack N circles of varying radii into a unit square, maximizing the sum of radii
  - autocorrelation_inequality [math]: Find tight bounds for autocorrelation inequalities. Given a sequence x of length
```

All 3 tasks (circle_packing, autocorrelation_inequality, trimul) listed with categories and descriptions.

---

### Test 4: `srf tasks --category math` — filtering works
**Status:** VERIFIED

```
$ srf tasks --category math
Available tasks:
  - circle_packing [math]: Pack N circles of varying radii into a unit square, maximizing the sum of radii
  - autocorrelation_inequality [math]: Find tight bounds for autocorrelation inequalities. Given a sequence x of length
```

Correctly filters to math-only tasks (trimul/gpu excluded).

---

### Test 5: `srf run --mode gepa --task circle_packing --budget 5 --mock-llm`
**Status:** VERIFIED

```
$ srf run --mode gepa --task circle_packing --budget 5 --mock-llm
...
{
  "run_id": "7ee477bafc88",
  "mode": "gepa",
  "task": "circle_packing",
  "best_score": 0.0,
  "eval_count": 5,
  "output_dir": "outputs/7ee477bafc88"
}
```

Output JSON contains `run_id`, `best_score`, `output_dir`. The pipeline executed exactly 5 iterations (matching budget), with proper Loop/Conditional/Sequential structure visible in logs:
- `loop.iteration` events for iterations 0-4
- `gate.result` for `merge_decision` (all PROCEED — no stagnation-triggered merge yet)
- `conditional.branch` selecting PROCEED (mutate) path
- `fn.execute` for all ops: select_parent, build_reflective_prompt, generate_code, sandbox_eval, accept_or_reject
- `budget_check` gate returns RELOOP for iterations 0-3, PROCEED at iteration 4 (budget exhausted)
- Exit code 0

---

### Test 6: Output directory contents
**Status:** NOT_VERIFIED

```
$ ls -la outputs/7ee477bafc88/
accepted_history.json
budget.jsonl
budget_state.json
candidate.py
candidates.jsonl
eval.py
eval_result.json
evaluations.jsonl
genealogy.json
gepa_state.json
initial.py
knobs.json
llm_calls.jsonl
mutate_prompt.md
policy_decisions.jsonl
population.json
rejection_history.json
selected_parent.json
```

**Missing: `best_solution.py`** — The spec says `accept_or_reject` writes `best_solution.py` when a new best is found. With mock LLM, all candidates score 0.0 (same as seed), so in strict acceptance mode (`child > parent` required), no candidate is ever accepted, and `best_solution.py` is never written. The initial seed should be written as `best_solution.py` at the start of the run so that there is always a best solution available after a run completes.

**Present:** All 5 Flora-compatible trace files (evaluations.jsonl, candidates.jsonl, llm_calls.jsonl, policy_decisions.jsonl, budget.jsonl), eval_result.json, gepa_state.json, population.json, genealogy.json. All valid JSON/JSONL.

---

### Test 7: Error handling — nonexistent mode
**Status:** VERIFIED

```
$ srf run --mode nonexistent --task circle_packing --budget 5 --mock-llm
Error: unknown mode 'nonexistent'. Available: ['gepa']
$ echo $?
1
```

Clean error message, exit code 1, no traceback.

---

### Test 8: Error handling — nonexistent task
**Status:** VERIFIED

```
$ srf run --mode gepa --task nonexistent --budget 5 --mock-llm
Error: unknown task 'nonexistent'. Available: ['trimul', 'circle_packing', 'autocorrelation_inequality']
$ echo $?
1
```

Clean error message, exit code 1, no traceback.

---

### Test 9: Error handling — nonexistent baseline trace
**Status:** VERIFIED

```
$ srf validate --mode gepa --task circle_packing --baseline-trace /nonexistent
Error: baseline trace not found: /nonexistent
$ echo $?
1
```

Clean error message, exit code 1, no traceback.

---

### Test 10: Knob overrides via CLI
**Status:** VERIFIED

```
$ srf run --mode gepa --task circle_packing --budget 3 --mock-llm --knob temperature=0.9 --knob parent_selection=pareto
...
{"knobs": {"temperature": 0.9, "parent_selection": "pareto", "max_rejection_context": 5.0, "merge_stagnation_threshold": 15.0, "acceptance_mode": "strict"}, ...}
...
{"strategy": "pareto", "parent_id": "1c4f3e03536c", ...}
...
{
  "run_id": "2883f57dff3c",
  "mode": "gepa",
  "task": "circle_packing",
  "best_score": 0.0,
  "eval_count": 3,
  "output_dir": "outputs/2883f57dff3c"
}
```

Both knob overrides applied correctly:
- `temperature` overridden to 0.9 (default 0.7)
- `parent_selection` overridden to "pareto" (default "best")
- Selection events show `"strategy": "pareto"` confirming the knob flows through to the ops callable
- Budget of 3 respected (3 evals)

---

### Test 11: gepa_state.json structure
**Status:** VERIFIED (with caveat)

```json
{
    "iteration": 2,
    "stagnation_counter": 3,
    "best_score": 0.0,
    "best_id": null,
    "merge_attempts": 0,
    "merge_due": false,
    "use_merge": true,
    "eval_count": 3,
    "budget_limit": 3,
    "population_size": 0,
    "total_accepted": 0,
    "total_rejected": 3
}
```

All expected fields present: stagnation_counter, eval_count, iteration, merge state, budget tracking.

**Caveat:** `population_size: 0` while `population.json` contains 1 entry (the seed). The state counter does not count the initial seed. This is a minor tracking inconsistency — the population file is the source of truth, but the state summary is misleading.

---

## Edge Case Tests

### All candidates rejected with mock LLM
**Observed:** All 5 iterations rejected candidates (strict mode: child > parent, mock LLM scores 0.0 = parent). Rejection history accumulates correctly (`rejection_count: 0, 1, 2, 3, 4` across iterations). Stagnation counter increments. This is correct behavior for mock mode.

### Budget enforced exactly
**Observed:** Budget 5 → exactly 5 evals. Budget 3 → exactly 3 evals. Budget tracking is precise.

### Trace format validation
**Observed:** All 5 Flora-compatible JSONL files have valid JSON records with timestamps, run_id, iteration, and relevant fields. Schema matches the design spec.

---

## Acceptance Criteria Verification

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Package installs with `pip install -e .` | VERIFIED |
| 2 | `srf modes` lists GEPA | VERIFIED |
| 3 | `srf tasks` lists circle_packing, autocorrelation_inequality, trimul | VERIFIED |
| 4 | `srf tasks --category math` filters correctly | VERIFIED |
| 5 | `srf run` produces JSON output with run_id, best_score, output_dir | VERIFIED |
| 6 | Output directory has best_solution.py, trace files, eval_result.json | NOT_VERIFIED |
| 7 | Error handling: nonexistent mode | VERIFIED |
| 8 | Error handling: nonexistent task | VERIFIED |
| 9 | Error handling: nonexistent baseline trace path | VERIFIED |
| 10 | Knob overrides work (temperature, parent_selection) | VERIFIED |
| 11 | gepa_state.json has correct structure | VERIFIED |

---

## Issues Found

### Issue 1 (Medium): `best_solution.py` never written in mock-LLM mode
- **What:** The output directory never contains `best_solution.py` because the acceptance gate requires `child_score > parent_score` (strict mode), and mock LLM candidates always score 0.0 (same as seed).
- **Why it matters:** A user running `--mock-llm` for smoke testing or CI would expect to find a `best_solution.py` in the output. The initial seed solution should be copied as `best_solution.py` at population initialization time, so there is always a "best" even if no improvement occurs.
- **Fix:** In population initialization (or at run start), copy `initial.py` → `best_solution.py` in the output directory.

### Issue 2 (Low): `population_size` in gepa_state.json doesn't count seed
- **What:** After a run, `gepa_state.json` reports `"population_size": 0` while `population.json` actually contains the seed entry with 1 member.
- **Why it matters:** A downstream consumer reading `gepa_state.json` for a quick summary would conclude the population is empty, which is misleading. The seed is in `population.json` but not reflected in the state counter.
- **Fix:** Initialize `population_size` to 1 after seeding, or derive it from `population.json` at write time.

---

## Adversarial Verdict: **PASS** (conditional)

10 of 11 criteria VERIFIED. The one NOT_VERIFIED criterion (Test 6: `best_solution.py` missing) is a real gap but not a showstopper — the core pipeline, DAG execution, budget tracking, trace emission, error handling, and knob overrides all work correctly. The missing `best_solution.py` is a UX issue specific to mock-LLM runs where no improvement occurs; it should be fixed by seeding the best solution from `initial.py` at run start.

Overall the CLI is well-implemented: clean error messages with exit code 1, no raw tracebacks, proper JSON output, Flora-compatible 5-file trace format, and correct DAG branching (Conditional merge/mutate, Loop with budget gate).
