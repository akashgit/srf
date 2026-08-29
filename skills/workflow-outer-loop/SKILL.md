---
name: workflow-outer-loop
description: "Outer loop evolutionary search — evolve workflow DAGs against benchmarks. Runs seed → evaluate → reflect → evolve → convergence gate with RELOOP. Terminal mode — does not chain to other modes. Use when the user says 'outer-loop', 'evolve workflows', or wants evolutionary search for optimal workflow topologies."
disable-model-invocation: true
argument-hint: "<project_path>"
---

# Outer Loop Workflow

The user wants: **$ARGUMENTS**

## Step: Seed

Initialize the evolutionary search. The CEO must track $GENERATION=0 after this step. All subsequent evaluate/reflect/evolve commands use the current $GENERATION value.

```bash
factory outer-loop calibrate $PROJECT_PATH
```

## Step: Evaluate

Substitute {generation} with the current $GENERATION value.

```bash
factory outer-loop evaluate $PROJECT_PATH --generation {generation}
```

## Step: Reflect

Substitute {generation} with the current $GENERATION value.

```bash
factory outer-loop reflect $PROJECT_PATH --generation {generation}
```

## Step: Evolve

Substitute {generation} with the current $GENERATION value. After this step completes, increment $GENERATION by 1.

```bash
factory outer-loop evolve $PROJECT_PATH --generation {generation}
```

### Gate — Converge (Automated)

**MANDATORY:** Wait for the preceding agent to finish, then run this check BEFORE spawning the next agent. Do NOT run agents in parallel across this gate.

```bash
factory outer-loop status $PROJECT_PATH --check-converge
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `promote`
- **RELOOP** (exit non-zero / FAIL in output) → return to `evaluate` for the next iteration.

*On RELOOP: return to `evaluate` (max 3 iterations)*

## Step: Promote

The search has converged. Read the status output to find the best mode name, then run: factory outer-loop promote {project_path} --mode-name <best_mode> --permanent-name evolved

```bash
factory outer-loop status $PROJECT_PATH
```
