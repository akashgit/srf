---
name: workflow-devopsgym
description: "Run the devopsgym workflow."
disable-model-invocation: true
argument-hint: "<project_path>"
---

# Devopsgym Workflow

The user wants: **$ARGUMENTS**

## Step: Study

```bash
mkdir -p $PROJECT_PATH/.factory/reviews && cd $PROJECT_PATH && (echo '=== Workspace ===' && ls -la && echo '\n=== Build Files ===' && find . -type f \( -name 'pom.xml' -o -name 'build.gradle' -o -name 'build.gradle.kts' -o -name 'go.mod' -o -name 'go.sum' -o -name 'Makefile' -o -name 'CMakeLists.txt' -o -name 'Dockerfile' -o -name 'docker-compose.yml' -o -name 'docker-compose.yaml' -o -name 'Jenkinsfile' -o -name 'Cargo.toml' -o -name 'package.json' -o -name 'requirements.txt' -o -name 'setup.py' \) | head -100 && echo '\n=== CI/CD Config ===' && find . -type f \( -name '*.yml' -o -name '*.yaml' \) -path '*/.github/workflows/*' | head -50 && find . -type f -name '.gitlab-ci.yml' | head -10 && echo '\n=== Source Files ===' && find . -type f \( -name '*.java' -o -name '*.go' -o -name '*.py' -o -name '*.rs' -o -name '*.c' -o -name '*.cpp' -o -name '*.sh' -o -name '*.bash' \) | head -100 && echo '\n=== Git ===' && git status 2>/dev/null || echo 'Not a git repository' && git log --oneline -10 2>/dev/null || true && echo '\n=== Task ===' && cat /tmp/task-instruction.md 2>/dev/null || echo 'No task instruction found at /tmp/task-instruction.md' && echo '\n=== Build System Detection ===' && echo 'Attempting to identify and run build...' && ([ -f pom.xml ] && echo 'Detected: Maven' && mvn --version 2>/dev/null || true) && ([ -f build.gradle ] || [ -f build.gradle.kts ] && echo 'Detected: Gradle' && gradle --version 2>/dev/null || true) && ([ -f go.mod ] && echo 'Detected: Go modules' && go version 2>/dev/null || true) && ([ -f Makefile ] && echo 'Detected: Make' || true) && ([ -f Dockerfile ] && echo 'Detected: Docker' || true)) > .factory/reviews/study-output.md 2>&1
```

## Phase 1: Builder — Solver

```bash
factory agent builder --task "You are solving a DevOps build/configuration task from the DevOps Gym benchmark.

## Your Task

1. **Read the task instruction** — Read /tmp/task-instruction.md carefully. Understand exactly what build or configuration issue needs to be fixed and what the expected behavior should be.

2. **Understand the project** — Check the study output at .factory/reviews/study-output.md for a structural overview. Examine build files (pom.xml, build.gradle, go.mod, Makefile, Dockerfile, CI/CD configs), source files, and any error logs.

3. **Analyze the build system** — Identify which build system is in use (Maven, Gradle, Go modules, Make, Docker, etc.). Understand the project's dependency structure, build targets, and configuration.

4. **Fix the issue** — Implement the fix described in the task instruction. This may involve modifying build configuration, fixing dependency declarations, updating CI/CD pipelines, fixing Dockerfiles, or adjusting build scripts.

5. **Verify the fix** — Attempt to build the project using the appropriate build tool. Verify the build succeeds and the configuration is correct.

6. **Commit your changes** — Commit directly on the current branch with a descriptive message. Do NOT create a new branch. Do NOT create a PR.

## Rules

- Act AUTONOMOUSLY — do NOT ask for confirmation or input
- PRESERVE the existing build system — do NOT switch build tools or modernize the build configuration unless explicitly asked. Fix ONLY the specific issue described in the task instruction.
- HIDDEN TESTS: The benchmark uses hidden verification steps. Do NOT hardcode outputs. Implement the general fix that solves the problem for any valid build configuration.
- Do NOT create branches or PRs — commit on current branch
- Do NOT run factory commands (factory eval, factory study, etc.)
- If something fails, investigate root cause and try alternative approaches

Read: .factory/reviews/study-output.md
Write output to: .factory/reviews/builder-latest.md" --project "$PROJECT_PATH" --timeout 7200
```

```bash
# Artifact verification: solver
_vfail=0
_f="$PROJECT_PATH/.factory/reviews/builder-latest.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: solver: .factory/reviews/builder-latest.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: solver: .factory/reviews/builder-latest.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=solver" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: solver artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=solver" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(harness verification — DO NOT SKIP)*

### Gate — Verify (Automated)

**MANDATORY:** Wait for the preceding agent to finish, then run this check BEFORE spawning the next agent. Do NOT run agents in parallel across this gate.

```bash
cd $PROJECT_PATH && CHANGES=$(git diff HEAD~1 --stat 2>/dev/null || echo 'NO_COMMITS') && if [ "$CHANGES" = 'NO_COMMITS' ] || [ -z "$CHANGES" ]; then echo 'fail: solver did not commit any changes'; exit 0; fi && if [ ! -f .factory/reviews/builder-latest.md ]; then echo 'fail: solver output missing'; exit 0; fi && BUILD_OK=0 && if [ -f pom.xml ]; then timeout 600 mvn compile -q 2>&1 && BUILD_OK=1 || { TAIL=$(timeout 600 mvn compile 2>&1 | tail -50); echo "reloop: Maven build failed — $TAIL"; exit 0; }; fi && if [ -f build.gradle ] || [ -f build.gradle.kts ]; then timeout 600 gradle build -q 2>&1 && BUILD_OK=1 || { TAIL=$(timeout 600 gradle build 2>&1 | tail -50); echo "reloop: Gradle build failed — $TAIL"; exit 0; }; fi && if [ -f go.mod ]; then timeout 600 go build ./... 2>&1 && BUILD_OK=1 || { TAIL=$(timeout 600 go build ./... 2>&1 | tail -50); echo "reloop: Go build failed — $TAIL"; exit 0; }; fi && if [ -f Makefile ]; then timeout 600 make 2>&1 && BUILD_OK=1 || { TAIL=$(timeout 600 make 2>&1 | tail -50); echo "reloop: Make build failed — $TAIL"; exit 0; }; fi && if [ $BUILD_OK -eq 0 ]; then echo 'pass: no recognized build system — deferring to Harbor verifier'; exit 0; fi && echo 'pass: build succeeded'
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `auto_merge`
- **RELOOP** (exit non-zero / FAIL in output) → return to `solver` for the next iteration.

*On RELOOP: return to `solver` (max 3 iterations)*

## Step: Auto Merge

```bash
cd $PROJECT_PATH && CURRENT=$(git rev-parse --abbrev-ref HEAD) && COMMON=$(git rev-parse --git-common-dir) && BASE=$(git --git-dir="$COMMON" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main) && if [ "$CURRENT" = "$BASE" ]; then echo "Already on $BASE — no merge needed"; exit 0; fi && git update-ref refs/heads/"$BASE" HEAD && PARENT_WT=$(cd "$COMMON/.." && pwd) && git diff-tree --no-commit-id --name-only -r HEAD HEAD~1 | while read file; do if [ -f "$file" ]; then mkdir -p "$PARENT_WT/$(dirname $file)" && cp "$file" "$PARENT_WT/$file"; fi; done && echo "Updated $BASE to $(git rev-parse --short HEAD)"
```
