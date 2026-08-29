---
name: workflow-salitrap
description: "Run the salitrap workflow."
disable-model-invocation: true
argument-hint: "<project_path>"
---

# Salitrap Workflow

The user wants: **$ARGUMENTS**

## Step: Study

```bash
mkdir -p $PROJECT_PATH/.factory/reviews && cd $PROJECT_PATH && (echo '=== Workspace Structure ===' && find . -type f | head -100 && echo '\n=== Task Instruction ===' && cat /tmp/task-instruction.md 2>/dev/null || echo 'No task instruction file found at /tmp/task-instruction.md') > .factory/reviews/study-output.md 2>&1
```

## Phase 1: Builder — Solver

```bash
factory agent builder --task "You are solving a commonsense reasoning task for the SaliTrap benchmark. The task instruction describes a real-world scenario that may contain SALIENCE TRAPS — numerical details designed to distract you from fundamental physical, environmental, temporal, or rule-based constraints.

## CRITICAL: Physics-Aware Reasoning

Before engaging with ANY numerical optimization or calculation, you MUST first verify the physical prerequisites of the scenario:
1. **Missing Prerequisites** — Does the scenario assume resources, tools, or conditions that are not actually present?
2. **Environmental Mismatch** — Is the proposed action physically possible in the described environment?
3. **Temporal/Physiological Violations** — Does the scenario require actions that violate biological limits or time constraints?
4. **Rule Mismatches** — Does the scenario ignore regulations, social norms, or logical rules?

If ANY prerequisite is violated, the correct answer is that the task is INFEASIBLE regardless of how optimal the numerical parameters might be. Do NOT be distracted by detailed numbers.

## Your Task

1. **Read the task instruction** — Read /tmp/task-instruction.md carefully. Identify the scenario and any embedded numerical distractors.

2. **Check physical prerequisites FIRST** — Before any calculation, verify that the fundamental assumptions of the scenario are physically valid. Ask: 'Can this actually happen in the real world as described?'

3. **Identify the trap dimension** — If a trap exists, classify it as one of: Missing Prerequisite, Environmental Mismatch, Temporal/Physiological Violation, or Rule Mismatch.

4. **Write your answer** — Write a structured answer to /workspace/answer.txt containing:
   - **Verdict:** feasible or infeasible
   - **Trap type:** (if infeasible) which trap dimension applies
   - **Reasoning:** step-by-step reasoning chain showing how you identified the trap or confirmed feasibility
   - **Key insight:** the specific physical/environmental/temporal/rule constraint that makes this infeasible (or why all prerequisites are met)

5. **Commit your answer** — Commit the answer file on the current branch.

## Rules

- Act AUTONOMOUSLY — do NOT ask for confirmation or input
- ALWAYS check physical prerequisites before numerical reasoning
- When in doubt about feasibility, lean toward INFEASIBLE — most scenarios in this benchmark contain hidden traps
- Do NOT create branches or PRs — commit on current branch
- Do NOT run factory commands (factory eval, factory study, etc.)
- Do NOT optimize numerical parameters if prerequisites are violated — state the violation directly

Read: .factory/reviews/study-output.md
Write output to: /workspace/answer.txt" --project "$PROJECT_PATH" --timeout 3600
```

```bash
# Artifact verification: solver
_vfail=0
_f="$PROJECT_PATH//workspace/answer.txt"
[ ! -f "$_f" ] && echo "VERIFY FAIL: solver: /workspace/answer.txt missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: solver: /workspace/answer.txt is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=solver" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: solver artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=solver" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(harness verification — DO NOT SKIP)*

### Gate — Verify (Automated)

**MANDATORY:** Wait for the preceding agent to finish, then run this check BEFORE spawning the next agent. Do NOT run agents in parallel across this gate.

```bash
cd $PROJECT_PATH && if [ ! -f /workspace/answer.txt ]; then echo 'reloop: answer.txt not found at /workspace/answer.txt'; exit 0; fi && if [ ! -s /workspace/answer.txt ]; then echo 'reloop: answer.txt is empty'; exit 0; fi && CHANGES=$(git diff HEAD~1 --stat 2>/dev/null || echo 'NO_COMMITS') && if [ "$CHANGES" = 'NO_COMMITS' ] || [ -z "$CHANGES" ]; then echo 'reloop: no commits found — solver must commit answer.txt'; exit 0; fi && echo 'pass: answer.txt exists with content and changes committed'
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `auto_merge`
- **RELOOP** (exit non-zero / FAIL in output) → return to `solver` for the next iteration.

*On RELOOP: return to `solver` (max 3 iterations)*

## Step: Auto Merge

```bash
cd $PROJECT_PATH && CURRENT=$(git rev-parse --abbrev-ref HEAD) && COMMON=$(git rev-parse --git-common-dir) && BASE=$(git --git-dir="$COMMON" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main) && if [ "$CURRENT" = "$BASE" ]; then echo "Already on $BASE — no merge needed"; exit 0; fi && git update-ref refs/heads/"$BASE" HEAD && PARENT_WT=$(cd "$COMMON/.." && pwd) && git diff-tree --no-commit-id --name-only -r HEAD HEAD~1 | while read file; do if [ -f "$file" ]; then mkdir -p "$PARENT_WT/$(dirname $file)" && cp "$file" "$PARENT_WT/$file"; fi; done && echo "Updated $BASE to $(git rev-parse --short HEAD)"
```
