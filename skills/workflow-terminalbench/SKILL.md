---
name: workflow-terminalbench
description: "Run the terminalbench workflow."
disable-model-invocation: true
argument-hint: "<project_path>"
---

# Terminalbench Workflow

The user wants: **$ARGUMENTS**

## Step: Study

```bash
mkdir -p $PROJECT_PATH/.factory/reviews && cd $PROJECT_PATH && (echo '=== Workspace ===' && ls -la && echo '\n=== Git ===' && git status 2>/dev/null || echo 'Not a git repository' && git log --oneline -10 2>/dev/null || true && echo '\n=== Languages ===' && (python3 --version 2>/dev/null || true) && (gcc --version 2>/dev/null | head -1 || true) && (g++ --version 2>/dev/null | head -1 || true) && (rustc --version 2>/dev/null || true) && (go version 2>/dev/null || true) && (node --version 2>/dev/null || true) && (java -version 2>&1 | head -1 || true) && (R --version 2>/dev/null | head -1 || true) && echo '\n=== Package Managers ===' && (which pip pip3 apt npm cargo gem luarocks 2>/dev/null || true) && echo '\n=== Tools ===' && (which make cmake git curl wget docker gdb strace ltrace valgrind sqlite3 ffmpeg openssl nmap 2>/dev/null || true) && echo '\n=== Task ===' && cat /tmp/task-instruction.md 2>/dev/null || echo 'No task instruction found at /tmp/task-instruction.md') > .factory/reviews/study-output.md 2>&1
```

## Phase 1: Builder

```bash
factory agent builder --task "You are solving a real-world engineering task in a terminal environment.

## Your Task

1. **Read the task instruction** — Read /tmp/task-instruction.md carefully. Understand exactly what the task is asking you to produce or accomplish, including any expected output format or success criteria.

2. **Understand the task type** — Tasks can range widely: building or debugging software, scientific computing, system administration, security analysis, data processing, ML model work, file format manipulation, mathematical computation, and more. Identify what kind of problem this is before diving in.

3. **Explore the environment** — Check what languages, compilers, tools, and package managers are available. Review the study output for an environment summary. Examine the workspace files and directory structure to understand what you are working with.

4. **Install dependencies** — If the task requires tools, libraries, or packages that are not already installed, install them using the available package manager (apt, pip, npm, cargo, etc.). Do this proactively before attempting the solution.

5. **Implement the solution** — Write code, compile programs, configure services, run analyses, execute commands — whatever the task requires. Work methodically: break complex tasks into steps and verify each step before moving on.

6. **Verify the result** — Test that your solution produces the expected output or achieves the expected outcome. Re-read the task instruction to confirm you have not missed any requirements.

7. **Commit your changes** — Commit directly on the current branch with a descriptive message. Do NOT create a new branch. Do NOT create a PR.

## Rules

- Act AUTONOMOUSLY — do NOT ask for confirmation or input
- Read the FULL task instruction before starting — details matter
- Install any missing dependencies proactively — do not assume they exist
- MUST verify the result matches expected output before committing
- Do NOT create branches or PRs — commit on current branch
- Do NOT run factory commands (factory eval, factory study, etc.)
- If something fails, investigate root cause and try alternative approaches
- If a tool or library is unavailable, find or build an alternative

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
cd $PROJECT_PATH && CHANGES=$(git diff HEAD~1 --stat 2>/dev/null || echo 'NO_COMMITS') && if [ "$CHANGES" = 'NO_COMMITS' ] || [ -z "$CHANGES" ]; then echo 'fail: builder did not commit any changes'; exit 0; fi && BUILDER_OUTPUT=$(cat .factory/reviews/builder-latest.md 2>/dev/null || echo '') && if echo "$BUILDER_OUTPUT" | grep -qiE '(pass|succeed|ok|complete|done|verified|correct|works)'; then echo 'pass: builder reports task completed successfully'; elif echo "$BUILDER_OUTPUT" | grep -qiE '(fail|error|broken|cannot|unable|wrong)'; then echo 'reloop: builder needs to retry — solution not confirmed'; else echo 'pass: changes committed, no failure signals detected'; fi
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `auto_merge`
- **RELOOP** (exit non-zero / FAIL in output) → return to `builder` for the next iteration.

*On RELOOP: return to `builder` (max 3 iterations)*

## Step: Auto Merge

```bash
cd $PROJECT_PATH && CURRENT=$(git rev-parse --abbrev-ref HEAD) && COMMON=$(git rev-parse --git-common-dir) && BASE=$(git --git-dir="$COMMON" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main) && if [ "$CURRENT" = "$BASE" ]; then echo "Already on $BASE — no merge needed"; exit 0; fi && git update-ref refs/heads/"$BASE" HEAD && PARENT_WT=$(cd "$COMMON/.." && pwd) && git diff-tree --no-commit-id --name-only -r HEAD HEAD~1 | while read file; do if [ -f "$file" ]; then mkdir -p "$PARENT_WT/$(dirname $file)" && cp "$file" "$PARENT_WT/$file"; fi; done && echo "Updated $BASE to $(git rev-parse --short HEAD)"
```
