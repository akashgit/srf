---
name: workflow-design
description: "Interactive design mode — build with a user approval gate at strategy, plus conditional study for existing projects. Use when the user says 'design X', 'plan X', 'let's discuss what to build', or wants to review the strategy before building. Works for both new and existing projects. Supports --from-plan to load an existing plan and skip research. With --just-plan, runs plan-only (research + strategy + GitHub publish, NO implementation)."
disable-model-invocation: true
argument-hint: "<project_path> [idea or spec] [--from-plan <path_or_url>] [--just-plan]"
---

# Design Workflow

The user wants: **$ARGUMENTS**

### Gate — Has Factory (Automated)

**MANDATORY:** Wait for the preceding agent to finish, then run this check BEFORE spawning the next agent. Do NOT run agents in parallel across this gate.

```bash
python3 -c "from pathlib import Path; exists = Path("$PROJECT_PATH/.factory/config.json").exists(); print("PROCEED" if exists else "HALT")"
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `graph_update`
- **HALT** (exit non-zero / FAIL in output) → continue to `discover` instead.

## Step: Discover

```bash
factory discover $PROJECT_PATH
```

### Gate — Factory Md Exists (Automated)

**MANDATORY:** Wait for the preceding agent to finish, then run this check BEFORE spawning the next agent. Do NOT run agents in parallel across this gate.

```bash
python3 -c "from pathlib import Path; exists = Path("$PROJECT_PATH/factory.md").exists(); print("PROCEED" if exists else "HALT")"
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `factory_init`
- **HALT** (exit non-zero / FAIL in output) → continue to `create_factory_md` instead.

## Phase 1: Ceo — Create Factory Md

```bash
factory agent ceo --task "Create factory.md from template. Copy the factory config template to the project root. Fill in: Goal, Scope, Guards, Eval command, Threshold, and Smoke Test. If .factory/eval_spec.json exists, populate the Eval Spec section. If .factory/strategy/current.md has a Research Configuration section, populate research sections (Research Target, Mutable/Fixed Surfaces, etc.).
Read: .factory/eval_profile.json
Write output to: factory.md" --project "$PROJECT_PATH" --timeout 3600
```

```bash
# Artifact verification: create_factory_md
_vfail=0
_f="$PROJECT_PATH/factory.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: create_factory_md: factory.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: create_factory_md: factory.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=create_factory_md" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: create_factory_md artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=create_factory_md" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(harness verification — DO NOT SKIP)*

## Step: Factory Init

Parse factory.md and generate .factory/config.json. Must run after factory.md is created.

```bash
factory init $PROJECT_PATH
```

## Step: Graph Update

Extract or incrementally update the code knowledge graph before study.

```bash
factory graph update $PROJECT_PATH
```

## Phase 2: Observe

Run local study to gather observations:

```bash
factory study $PROJECT_PATH
```

Writes observations to `.factory/strategy/observations.md`.

If your task includes a focus directive or focus topic, pass it to the study command:
`factory study $PROJECT_PATH --focus "<your focus topic>"`

## Phase 3: Researcher — Graph Explorer

```bash
factory agent researcher --task "Explore the project's code knowledge graph to build structural understanding. Read .factory/strategy/observations.md for focus context.

**Step 0 — detect graph availability:** Your working directory is already the project root. The graph file lives at `$PROJECT_PATH/graph.json` (NOT inside `.factory/`). Run this smoke check FIRST — use a relative path since your CWD is the project root: `test -f graph.json && echo 'GRAPH AVAILABLE' || echo 'NO GRAPH'` — if the output says GRAPH AVAILABLE, proceed with the graph commands below. If the output says NO GRAPH, skip to the fallback section.

**If the graph IS available:**
1. Run `factory graph query "$PROJECT_PATH" "<focus from observations>" --depth 2` to find relevant nodes
2. Run `factory graph explain "$PROJECT_PATH" "<key node>"` on the most important nodes to understand their connections and dependencies
3. Run `factory graph path "$PROJECT_PATH" "<A>" "<B>"` to trace dependency paths between key components
4. Write structured findings to .factory/strategy/graph-context.md covering: key modules and their relationships, dependency paths, architectural layers, entry points and hotspots

**If the graph is NOT available**, fall back to direct file exploration:
1. Use `find . -name '*.py' | head -50` to discover source files
2. Use `grep -rn 'class \|def ' --include='*.py' | head -100` to map functions and classes
3. Use `grep -rn 'import ' --include='*.py' | head -100` to trace dependencies
4. Write the same structured findings to .factory/strategy/graph-context.md
Read: .factory/strategy/observations.md
Write output to: .factory/strategy/graph-context.md" --project "$PROJECT_PATH" --timeout 600
```

```bash
# Artifact verification: graph_explorer
_vfail=0
_f="$PROJECT_PATH/.factory/strategy/graph-context.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: graph_explorer: .factory/strategy/graph-context.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: graph_explorer: .factory/strategy/graph-context.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=graph_explorer" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: graph_explorer artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=graph_explorer" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(harness verification — DO NOT SKIP)*

## Step: Concat Study

```bash
cat $PROJECT_PATH/.factory/strategy/observations.md $PROJECT_PATH/.factory/strategy/graph-context.md > $PROJECT_PATH/.factory/strategy/study-combined.md
```

## Phase 4: Research (Parallel)

Spawn 3 agents in parallel:

```bash
factory agent researcher --review-tag similar --task "Similar projects research. Read .factory/strategy/study-combined.md for project context (observations + structural graph analysis). Search the web for similar projects, existing solutions, and prior art. Analyze their strengths, weaknesses, and market positioning. Check .factory/archive/ for prior knowledge on similar builds. Write findings to .factory/strategy/research-similar.md covering: similar projects found (with links), what they do well and what's missing, differentiation opportunities.
Read: .factory/strategy/study-combined.md
Write output to: .factory/strategy/research-similar.md" --project "$PROJECT_PATH" --timeout 600 &
```

```bash
factory agent researcher --review-tag techstack --task "Tech stack research. Read .factory/strategy/study-combined.md for project context (observations + structural graph analysis). Identify the best technology stack for this type of project. Find architecture patterns and best practices. Evaluate framework/library options with trade-offs. Write findings to .factory/strategy/research-techstack.md covering: recommended tech stack with rationale, architecture patterns, framework comparisons.
Read: .factory/strategy/study-combined.md
Write output to: .factory/strategy/research-techstack.md" --project "$PROJECT_PATH" --timeout 600 &
```

```bash
factory agent researcher --review-tag pitfalls --task "Pitfalls and scope research. Read .factory/strategy/study-combined.md for project context (observations + structural graph analysis). Identify potential pitfalls and common mistakes for this type of project. Research MVP scope best practices. Check .factory/archive/ for lessons from past builds. Write findings to .factory/strategy/research-pitfalls.md covering: potential pitfalls to avoid, MVP scope recommendation, lessons from similar past builds.
Read: .factory/strategy/study-combined.md
Write output to: .factory/strategy/research-pitfalls.md" --project "$PROJECT_PATH" --timeout 600 &
```

```bash
wait
```

**Important:** Run ALL commands above in a **single** Bash tool call with timeout set to at least 600 seconds.

```bash
# Artifact verification: researcher_similar
_vfail=0
_f="$PROJECT_PATH/.factory/strategy/research-similar.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: researcher_similar: .factory/strategy/research-similar.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: researcher_similar: .factory/strategy/research-similar.md is empty" && _vfail=1
[ -f "$_f" ] && [ "$(wc -c < "$_f")" -lt 50 ] && echo "VERIFY FAIL: researcher_similar: .factory/strategy/research-similar.md smaller than 50 bytes" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=researcher_similar" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: researcher_similar artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=researcher_similar" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"

# Artifact verification: researcher_techstack
_vfail=0
_f="$PROJECT_PATH/.factory/strategy/research-techstack.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: researcher_techstack: .factory/strategy/research-techstack.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: researcher_techstack: .factory/strategy/research-techstack.md is empty" && _vfail=1
[ -f "$_f" ] && [ "$(wc -c < "$_f")" -lt 50 ] && echo "VERIFY FAIL: researcher_techstack: .factory/strategy/research-techstack.md smaller than 50 bytes" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=researcher_techstack" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: researcher_techstack artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=researcher_techstack" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"

# Artifact verification: researcher_pitfalls
_vfail=0
_f="$PROJECT_PATH/.factory/strategy/research-pitfalls.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: researcher_pitfalls: .factory/strategy/research-pitfalls.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: researcher_pitfalls: .factory/strategy/research-pitfalls.md is empty" && _vfail=1
[ -f "$_f" ] && [ "$(wc -c < "$_f")" -lt 50 ] && echo "VERIFY FAIL: researcher_pitfalls: .factory/strategy/research-pitfalls.md smaller than 50 bytes" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=researcher_pitfalls" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: researcher_pitfalls artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=researcher_pitfalls" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(post-barrier harness verification — DO NOT SKIP)*

## Barrier: Research

Wait for all parallel agents to complete: `researcher_similar`, `researcher_techstack`, `researcher_pitfalls`

### CEO Review — Research

Apply the CEO Review Gate protocol:
1. Read the agent output for the preceding step
2. Read artifacts: `.factory/strategy/research-pitfalls.md`, `.factory/strategy/research-similar.md`, `.factory/strategy/research-techstack.md`
3. Assess: Is the research relevant? Does it cover the technology landscape adequately? Check for gaps in similar projects, tech stack analysis, and pitfall coverage.
4. Write verdict to `.factory/reviews/ceo-verdict-research.md`
5. **PROCEED** → continue to next step
6. **REDIRECT** → re-invoke the preceding agent with corrections (max 2)
7. **ABORT** → log failure and skip to archival

*On RELOOP: return to `fork_research` (max 3 iterations)*

## Phase 5: Strategist

```bash
factory agent strategist --task "Synthesize a project specification from study and research. If .factory/strategy/study-combined.md exists, read it for project observations and structural graph analysis. Read ALL research files at .factory/strategy/research-similar.md, research-techstack.md, and research-pitfalls.md. Produce a complete phased build plan. Phase 1 must be project scaffold + eval harness. Every Phase must have substantive What/Why/Expected impact fields. Build EVERYTHING in this pass. Only defer items requiring human intervention. Write the plan to .factory/strategy/current.md.
Read: .factory/strategy/research-pitfalls.md, .factory/strategy/research-similar.md, .factory/strategy/research-techstack.md, .factory/strategy/study-combined.md
Write output to: .factory/strategy/current.md" --project "$PROJECT_PATH" --timeout 600
```

```bash
# Artifact verification: strategist
_vfail=0
_f="$PROJECT_PATH/.factory/strategy/current.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: strategist: .factory/strategy/current.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: strategist: .factory/strategy/current.md is empty" && _vfail=1
[ -f "$_f" ] && [ "$(wc -c < "$_f")" -lt 200 ] && echo "VERIFY FAIL: strategist: .factory/strategy/current.md smaller than 200 bytes" && _vfail=1
[ -f "$_f" ] && ! grep -qE '\#\#\#\ Phase\ 1|\#\#\#\ Architecture' "$_f" && echo "VERIFY FAIL: strategist: .factory/strategy/current.md missing required sentinel (### Phase 1, ### Architecture)" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=strategist" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: strategist artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=strategist" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(harness verification — DO NOT SKIP)*

### Steering Point — Strategy (User Approval)

**This is a USER approval gate, NOT a CEO review gate. Do NOT self-approve.**

Present the strategy/findings to the user by summarizing key points in your output.
Then explicitly ask the user: "Do you approve this plan, or do you have feedback?"

**You MUST wait for the user's response before proceeding.**
- The user says "approve", "yes", "looks good", or similar → proceed to next step
- The user provides feedback or corrections → re-run the previous step incorporating their feedback
- Do NOT write a verdict file and auto-proceed — this gate requires human input

*On RELOOP: return to `strategist` (max 3 iterations)*

## Phase 6: Archivist Plan

```bash
factory agent archivist --task "Archive the approved research and strategy.
Read: .factory/strategy/current.md
Write output to: .factory/archive/plan.md" --project "$PROJECT_PATH" --timeout 300 --model haiku &
```
*(fire-and-forget — CEO continues immediately)*

## Phase 7: Builder

```bash
factory agent builder --task "Implement the next phase from .factory/strategy/current.md. Read the CEO's plan approval at .factory/reviews/ceo-verdict-strategist.md. Read CLAUDE.md and factory.md if they exist. Implement exactly what the current phase describes. Run tests. Commit changes and open a draft PR.
Read: .factory/strategy/current.md
Write output to: .factory/reviews/builder-latest.md" --project "$PROJECT_PATH" --timeout 1200
```

```bash
# Artifact verification: builder
_vfail=0
_f="$PROJECT_PATH/.factory/reviews/builder-latest.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: builder: .factory/reviews/builder-latest.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: builder: .factory/reviews/builder-latest.md is empty" && _vfail=1
[ -f "$_f" ] && [ "$(wc -c < "$_f")" -lt 500 ] && echo "VERIFY FAIL: builder: .factory/reviews/builder-latest.md smaller than 500 bytes" && _vfail=1
[ -f "$_f" ] && ! grep -qE 'commit' "$_f" && echo "VERIFY FAIL: builder: .factory/reviews/builder-latest.md missing required sentinel (commit)" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=builder" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: builder artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=builder" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(harness verification — DO NOT SKIP)*

### CEO Review — Build

Apply the CEO Review Gate protocol:
1. Read the agent output for the preceding step
2. Read artifacts: `.factory/reviews/builder-latest.md`
3. Assess: Read builder output. Check git log and diff. Does the work match the plan for this phase? If the Builder opened a PR, read it. REDIRECT if off-scope or missed key requirements.
4. Write verdict to `.factory/reviews/ceo-verdict-build.md`
5. **PROCEED** → continue to next step
6. **REDIRECT** → re-invoke the preceding agent with corrections (max 2)
7. **ABORT** → log failure and skip to archival

*On RELOOP: return to `builder` (max 3 iterations)*

## Phase 8: Qa (Parallel)

Spawn 3 agents in parallel:

```bash
factory agent health_checker --task "Execute health_checker task for the project.
Read: .factory/reviews/builder-latest.md, .factory/strategy/current.md
Write output to: .factory/reviews/health-check.md" --project "$PROJECT_PATH" --timeout 600 &
```

```bash
factory agent code_reviewer --task "Execute code_reviewer task for the project.
Read: .factory/reviews/builder-latest.md, .factory/strategy/current.md
Write output to: .factory/reviews/code-review.md" --project "$PROJECT_PATH" --timeout 900 &
```

```bash
factory agent adversarial_tester --task "Execute adversarial_tester task for the project.
Read: .factory/reviews/builder-latest.md, .factory/strategy/current.md
Write output to: .factory/reviews/adversarial-qa.md" --project "$PROJECT_PATH" --timeout 1800 &
```

```bash
wait
```

**Important:** Run ALL commands above in a **single** Bash tool call with timeout set to at least 1800 seconds.

```bash
# Artifact verification: health_checker
_vfail=0
_f="$PROJECT_PATH/.factory/reviews/health-check.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: health_checker: .factory/reviews/health-check.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: health_checker: .factory/reviews/health-check.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=health_checker" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: health_checker artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=health_checker" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"

# Artifact verification: code_reviewer
_vfail=0
_f="$PROJECT_PATH/.factory/reviews/code-review.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: code_reviewer: .factory/reviews/code-review.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: code_reviewer: .factory/reviews/code-review.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=code_reviewer" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: code_reviewer artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=code_reviewer" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"

# Artifact verification: adversarial_tester
_vfail=0
_f="$PROJECT_PATH/.factory/reviews/adversarial-qa.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: adversarial_tester: .factory/reviews/adversarial-qa.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: adversarial_tester: .factory/reviews/adversarial-qa.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=adversarial_tester" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: adversarial_tester artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=adversarial_tester" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(post-barrier harness verification — DO NOT SKIP)*

## Barrier: Qa

Wait for all parallel agents to complete: `health_checker`, `code_reviewer`, `adversarial_tester`

Read combined outputs: `.factory/reviews/adversarial-qa.md`, `.factory/reviews/code-review.md`, `.factory/reviews/health-check.md`

### CEO Review — Qa

Apply the CEO Review Gate protocol:
1. Read the agent output for the preceding step
2. Read artifacts: `.factory/reviews/adversarial-qa.md`, `.factory/reviews/code-review.md`, `.factory/reviews/health-check.md`
3. Assess: Review QA results. PROCEED if all checks pass. RELOOP to builder (max 3 iterations) if issues found.
4. Write verdict to `.factory/reviews/ceo-verdict-qa.md`
5. **PROCEED** → continue to next step
6. **REDIRECT** → re-invoke the preceding agent with corrections (max 2)
7. **ABORT** → log failure and skip to archival

*On RELOOP: return to `builder` (max 3 iterations)*

### CEO Review — Doc Freshness

Apply the CEO Review Gate protocol:
1. Read the agent output for the preceding step
2. Read artifacts: `.factory/reviews/adversarial-qa.md`
3. Assess: Check the PR diff for documentation freshness. If public APIs, CLI commands, configuration options, or architecture were changed or added, corresponding documentation (README.md, CLAUDE.md, docstrings, --help text, or doc/ files) MUST be updated. PROCEED if docs are current or no doc-worthy changes exist. RELOOP to builder if documentation is stale — specify exactly which changes need doc updates.
4. Write verdict to `.factory/reviews/ceo-verdict-doc-freshness.md`
5. **PROCEED** → continue to next step
6. **REDIRECT** → re-invoke the preceding agent with corrections (max 2)
7. **ABORT** → log failure and skip to archival

*On RELOOP: return to `builder` (max 3 iterations)*

### Gate — Precheck (Automated)

**MANDATORY:** Wait for the preceding agent to finish, then run this check BEFORE spawning the next agent. Do NOT run agents in parallel across this gate.

```bash
factory precheck $PROJECT_PATH --score-before 0 --score-after 0
```

- **PROCEED** (exit 0 / no FAIL in output) → continue to `archivist_build`
- **HALT** (exit non-zero / FAIL in output) → continue to `archivist_build` instead.

## Phase 9: Archivist Build

```bash
factory agent archivist --task "Archive the build phase results.
Read: .factory/reviews/adversarial-qa.md
Write output to: .factory/archive/build.md" --project "$PROJECT_PATH" --timeout 300 --model haiku &
```
*(fire-and-forget — CEO continues immediately)*

## Step: Spec Generate

Generate the project specification via the gated spec-generate workflow. Runs non-blocking after archival.

```bash
factory workflow run spec-generate $PROJECT_PATH
```
