---
name: workflow-legacybench
description: "Run the legacybench workflow."
disable-model-invocation: true
argument-hint: "<project_path>"
---

# Legacybench Workflow

The user wants: **$ARGUMENTS**

## Step: Study

```bash
mkdir -p $PROJECT_PATH/.factory/reviews && cd $PROJECT_PATH && (echo '=== Workspace ===' && ls -la && echo '\n=== Source Files ===' && find . -type f \( -name '*.c' -o -name '*.h' -o -name '*.f' -o -name '*.f90' -o -name '*.cob' -o -name '*.cbl' -o -name '*.java' -o -name '*.s' -o -name '*.asm' -o -name '*.py' \) | head -100 && echo '\n=== Git ===' && git status 2>/dev/null || echo 'Not a git repository' && git log --oneline -10 2>/dev/null || true && echo '\n=== Build System ===' && cat Makefile 2>/dev/null || true && ls -la *.sh build* configure* 2>/dev/null || true && echo '\n=== Test Files ===' && find . -type f \( -name 'test*' -o -name '*test*' -o -name '*spec*' \) 2>/dev/null | head -50 || true && echo '\n=== Task ===' && cat /tmp/task-instruction.md 2>/dev/null || echo 'No task instruction found at /tmp/task-instruction.md' && echo '\n=== Output Format Analysis ===' && echo 'Attempting to build and capture output format...' && (make 2>/dev/null && echo 'Build succeeded' || true)) > .factory/reviews/study-output.md 2>&1
```

## Phase 1: Builder

```bash
factory agent builder --task "You are fixing a bug in legacy code for the Legacy-Bench benchmark.

## Your Task

1. **Read the task instruction** — Read /tmp/task-instruction.md carefully. Understand exactly what bug needs to be fixed and what the expected behavior should be.

2. **Understand the codebase** — Check the study output at .factory/reviews/study-output.md for a structural overview. Read the source files, Makefile, and any test scripts.

3. **Analyze the output format** — If the program produces output, understand the EXACT format: field widths, decimal places, alignment, separators, headers/footers. Output format mismatches are a common failure mode.

4. **Fix the bug** — Implement the fix described in the task instruction.

5. **Verify the fix** — Build and run the program. Verify your fix works on at least 3 different inputs (visible examples + 2 you construct).

6. **Commit your changes** — Commit directly on the current branch with a descriptive message. Do NOT create a new branch. Do NOT create a PR.

## Rules

- Act AUTONOMOUSLY — do NOT ask for confirmation or input
- LEGACY CODE: Preserve the EXACT original language standard and coding patterns. Do NOT modernize syntax, idioms, or libraries. Fix ONLY the specific bug described in the task instruction. If the bug requires changing a data type, use the equivalent type from the ORIGINAL language standard.
- HIDDEN TESTS: The benchmark uses hidden test inputs beyond the visible examples. Do NOT hardcode output to match reference examples. Implement the general algorithm that solves the problem for ANY valid input.
- Do NOT create branches or PRs — commit on current branch
- Do NOT run factory commands (factory eval, factory study, etc.)
- If something fails, investigate root cause and try alternative approaches

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
cd $PROJECT_PATH && CHANGES=$(git diff HEAD~1 --stat 2>/dev/null || echo 'NO_COMMITS') && if [ "$CHANGES" = 'NO_COMMITS' ] || [ -z "$CHANGES" ]; then echo 'fail: builder did not commit any changes'; exit 0; fi && if [ ! -f .factory/reviews/builder-latest.md ]; then echo 'fail: builder output missing'; exit 0; fi && if [ ! -f Makefile ]; then echo 'reloop: no Makefile found — cannot independently verify correctness'; exit 0; fi && BUILD_OUT=$(timeout 600 make 2>&1) || { TAIL=$(echo "$BUILD_OUT" | tail -50); echo "reloop: compilation failed — $TAIL"; exit 0; } && TEST_PROBE=$(make -n test 2>&1); if [ $? -ne 0 ]; then echo 'reloop: no test target in Makefile — cannot verify correctness'; exit 0; fi && TEST_OUT=$(timeout 600 make test 2>&1) || { TAIL=$(echo "$TEST_OUT" | tail -50); echo "reloop: tests failed — $TAIL"; exit 0; } && echo 'pass: compilation and tests succeeded'
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `auto_merge`
- **RELOOP** (exit non-zero / FAIL in output) → return to `builder` for the next iteration.

*On RELOOP: return to `builder` (max 3 iterations)*

## Step: Auto Merge

```bash
cd $PROJECT_PATH && CURRENT=$(git rev-parse --abbrev-ref HEAD) && COMMON=$(git rev-parse --git-common-dir) && BASE=$(git --git-dir="$COMMON" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main) && if [ "$CURRENT" = "$BASE" ]; then echo "Already on $BASE — no merge needed"; exit 0; fi && git update-ref refs/heads/"$BASE" HEAD && PARENT_WT=$(cd "$COMMON/.." && pwd) && git diff-tree --no-commit-id --name-only -r HEAD HEAD~1 | while read file; do if [ -f "$file" ]; then mkdir -p "$PARENT_WT/$(dirname $file)" && cp "$file" "$PARENT_WT/$file"; fi; done && echo "Updated $BASE to $(git rev-parse --short HEAD)"
```
