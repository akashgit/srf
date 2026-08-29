---
name: workflow-tomswe
description: "Run the tomswe workflow."
disable-model-invocation: true
argument-hint: "<project_path>"
---

# Tomswe Workflow

The user wants: **$ARGUMENTS**

## Step: Study

```bash
mkdir -p $PROJECT_PATH/.factory/reviews && cd $PROJECT_PATH && (echo '=== Repository Structure ===' && find . -type f -name '*.py' | head -200 && echo '\n=== Test Files ===' && find . -type f -name 'test_*.py' -o -name '*_test.py' | head -50 && echo '\n=== Configuration Files ===' && ls -la setup.py setup.cfg pyproject.toml tox.ini conftest.py 2>/dev/null || true && echo '\n=== Task Instruction ===' && cat /tmp/task-instruction.md 2>/dev/null || echo 'No task instruction file found at /tmp/task-instruction.md') > .factory/reviews/study-output.md 2>&1
```

## Phase 1: Builder

```bash
factory agent builder --task "You are solving a task for the ToM-SWE benchmark. The task instruction contains DELIBERATELY VAGUE requirements and a user profile describing the user's coding preferences and interaction style.

## Your Task

1. **Read the task instruction** — Read /tmp/task-instruction.md. Extract BOTH the vague task description AND the user profile section.

2. **Infer user intent** — Determine what the user actually wants from the vague description by analyzing context clues, surrounding code patterns, and the user profile.

3. **Apply user preferences** — Follow the user's coding style (naming conventions, testing approach, git workflow, documentation habits) as described in the profile.

4. **Explore the codebase** — Read relevant source files, test files, and configuration to understand the project structure.

5. **Implement the solution** — Make changes that align with BOTH the inferred task requirements AND the user's preferred coding style.

6. **Run tests** — Verify the fix works and existing tests still pass. Use pytest, tox, or whatever test runner the project uses.

7. **Commit your changes** — Commit directly on the current branch with a message following the user's commit convention preferences (if specified in the profile).

## Rules

- When instructions are vague, infer the most likely intent from context — do NOT ask for clarification
- Follow the user's coding preferences from the profile section
- Prefer the user's preferred tools/libraries when multiple options exist
- MUST run tests before committing — never commit untested code
- Do NOT create branches or PRs — commit on current branch
- Do NOT run factory commands (factory eval, factory study, etc.)
- Do NOT modify test files unless the task requires it
- If tests fail after your fix, investigate and fix the issue

Read: .factory/reviews/study-output.md
Write output to: .factory/reviews/builder-latest.md" --project "$PROJECT_PATH" --timeout 7200
```

```bash
# Artifact verification: builder
_vfail=0
_f="$PROJECT_PATH/.factory/reviews/builder-latest.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: builder: .factory/reviews/builder-latest.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: builder: .factory/reviews/builder-latest.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=builder" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: builder artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=builder" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(harness verification — DO NOT SKIP)*

### Gate — Verify (Automated)

**MANDATORY:** Wait for the preceding agent to finish, then run this check BEFORE spawning the next agent. Do NOT run agents in parallel across this gate.

```bash
cd $PROJECT_PATH && CHANGES=$(git diff HEAD~1 --stat 2>/dev/null || echo 'NO_COMMITS') && if [ "$CHANGES" = 'NO_COMMITS' ] || [ -z "$CHANGES" ]; then echo 'fail: builder did not commit any changes'; exit 0; fi && BUILDER_OUTPUT=$(cat .factory/reviews/builder-latest.md 2>/dev/null || echo '') && if echo "$BUILDER_OUTPUT" | grep -qiE 'tests?.*(pass|succeed|ok|PASSED)'; then echo 'pass: builder reports tests passing'; elif echo "$BUILDER_OUTPUT" | grep -qiE 'tests?.*(fail|error|FAILED)'; then echo 'reloop: builder needs to retry — tests did not pass'; else echo 'pass: changes committed, no issues detected'; fi
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `auto_merge`
- **RELOOP** (exit non-zero / FAIL in output) → return to `builder` for the next iteration.

*On RELOOP: return to `builder` (max 3 iterations)*

## Step: Auto Merge

```bash
cd $PROJECT_PATH && CURRENT=$(git rev-parse --abbrev-ref HEAD) && COMMON=$(git rev-parse --git-common-dir) && BASE=$(git --git-dir="$COMMON" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main) && if [ "$CURRENT" = "$BASE" ]; then echo "Already on $BASE — no merge needed"; exit 0; fi && git update-ref refs/heads/"$BASE" HEAD && PARENT_WT=$(cd "$COMMON/.." && pwd) && git diff-tree --no-commit-id --name-only -r HEAD HEAD~1 | while read file; do if [ -f "$file" ]; then mkdir -p "$PARENT_WT/$(dirname $file)" && cp "$file" "$PARENT_WT/$file"; fi; done && echo "Updated $BASE to $(git rev-parse --short HEAD)"
```
