---
name: workflow-featurebench
description: "Run the featurebench workflow."
disable-model-invocation: true
argument-hint: "<project_path>"
---

# Featurebench Workflow

The user wants: **$ARGUMENTS**

## Step: Study

```bash
mkdir -p $PROJECT_PATH/.factory/reviews && cd $PROJECT_PATH && (echo '=== Repository Structure ===' && find . -type f -name '*.py' | head -200 && echo '\n=== Package Layout ===' && find . -type d -name '__pycache__' -prune -o -type d -print | head -50 && echo '\n=== Test Files ===' && find . -type f -name 'test_*.py' -o -name '*_test.py' | head -50 && echo '\n=== Configuration Files ===' && ls -la setup.py setup.cfg pyproject.toml tox.ini conftest.py 2>/dev/null || true && echo '\n=== Placeholder Implementations ===' && grep -rl 'NotImplementedError\|^\s*pass$' --include='*.py' . 2>/dev/null | head -50 || true && echo '\n=== Task Instruction ===' && cat /tmp/task-instruction.md 2>/dev/null || echo 'No task instruction file found at /tmp/task-instruction.md') > .factory/reviews/study-output.md 2>&1
```

## Phase 1: Builder

```bash
factory agent builder --task "You are implementing a new feature in a Python codebase for the FeatureBench benchmark.

## Your Task

1. **Read the FULL task description** — Read /tmp/task-instruction.md carefully. It contains detailed interface specifications: function signatures, import paths, input/output types, and expected behavior. These specs are the contract your code must satisfy.

2. **Understand the existing codebase** — Explore the repository structure thoroughly. Read related source files, understand module layout, imports, and existing patterns. Check the study output at .factory/reviews/study-output.md for a structural overview.

3. **CRITICAL: Read before you write** — Before implementing ANY function, navigate to and READ the actual source code for every function, class, or module you reference. DO NOT guess function signatures, import paths, or class attributes. The most common failure mode is agents hallucinating interfaces instead of reading the actual code — NameError and ImportError from wrong cross-file references.

4. **Implement the feature** — Follow the specified interfaces EXACTLY: match function names, parameter names, types, return types, and import paths precisely. The evaluation checks that your code is directly callable via the specified interface.

5. **Handle cross-file dependencies** — If the feature spans multiple files, ensure ALL imports and references resolve correctly. Check that every module you import exists, every function you call is defined, and every class attribute you access is real.

6. **Run the project's test suite** — Execute the tests to verify your implementation. Look specifically for NameError, ImportError, and TypeError in test output — these are signals of missing cross-file connections or interface mismatches.

7. **Iterate on test failures** — If tests fail, trace the error to its root cause. Fix missing dependencies, correct interface mismatches, and re-run until tests pass.

8. **Commit your changes** — Commit directly on the current branch with a descriptive message. Do NOT create a new branch. Do NOT create a PR.

## Rules

- Act AUTONOMOUSLY — do NOT ask for confirmation or input
- Follow interface specs EXACTLY — the evaluation checks that your code is directly callable via the specified signatures and import paths
- Do NOT modify test files
- Do NOT guess — READ the actual source code for any function/class you reference
- If tests fail with NameError or ImportError, trace the missing dependency and fix it
- If tests fail with TypeError, check that your function signatures match the specs exactly
- Do NOT create branches or PRs — commit on current branch
- Do NOT run factory commands (factory eval, factory study, etc.)

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
