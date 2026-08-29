---
name: workflow-create
description: "Create mode — meta-mode for creating new factory modes or updating existing ones. For new modes: takes a description and produces a fully working workflow definition, SKILL.md, CLI wiring, and tests. For updates: use --focus "mode_name: change description" to modify an existing registered mode (e.g. --focus "improve: add plateau detection"). Use when the user says 'create a mode for X', 'update the improve mode', 'add a new workflow', or wants to extend/modify factory pipelines."
disable-model-invocation: true
argument-hint: ""mode description" or "existing_mode: change description""
---

# Create Workflow

The user wants: **$ARGUMENTS**

## Phase 1: Research (Parallel)

Spawn 3 agents in parallel:

```bash
factory agent researcher --review-tag existing --task "Existing workflow analysis. If the CEO task includes '## Create Mode (Update Existing Mode)', read the **Target mode:** field and focus your analysis on that specific mode's workflow definition via `factory workflow show <target_mode>`. Document its current node sequences, gate logic, edge wiring, trigger function, and reads/writes. Also read its SKILL.md at skills/workflow-<target_mode>/SKILL.md for the generated playbook. Otherwise, read factory/workflow/definitions.py and analyze all existing workflow definitions (build, design, create, spec-generate). Document common patterns: node sequences, gate conventions, fork/join patterns, archivist placement, edge wiring, trigger functions, reads/writes declarations. Read factory/workflow/primitives.py for available node types and their fields. Read factory/workflow/skill_export.py for WORKFLOW_META format. Write findings to .factory/strategy/research-existing.md covering: node type usage patterns, common subgraphs (builder→gate→qa→gate loop), trigger function conventions, data flow patterns.
Write output to: .factory/strategy/research-existing.md" --project "$PROJECT_PATH" --timeout 600 &
```

```bash
factory agent researcher --review-tag intent --task "Mode description analysis. Read the user's mode description from the CEO task. If the CEO task includes '## Create Mode (Plugin Package)', parse the **output_folder** and plugin-specific constraints (standalone package, entry point registration, no upstream modifications). Structure the plugin packaging requirements: pyproject.toml entry point, workflow file layout, register_plugin() function pattern, installation and verification steps. Write findings to .factory/strategy/research-intent.md covering: structured requirements, packaging needs, workflow node candidates. Otherwise, if the CEO task includes '## Create Mode (Update Existing Mode)', parse the **Requested changes:** field and structure the requested modifications against the existing mode's current behavior. Identify which nodes, edges, prompts, or gates need to change and which must remain untouched. Otherwise, parse and structure the description into a new workflow specification: - Purpose and trigger conditions - Agent roles needed (which specialists) - Gate logic (user vs agent vs fn evaluators) - Data flow (what files are read/written) - Interactive vs headless requirements - Input format (text, file, drawing, flow) Write findings to .factory/strategy/research-intent.md covering: structured requirements, node candidates, suggested graph topology.
Write output to: .factory/strategy/research-intent.md" --project "$PROJECT_PATH" --timeout 600 &
```

```bash
factory agent researcher --review-tag practices --task "Workflow design best practices. Search the web for workflow and pipeline design patterns relevant to the described mode. Look for: DAG design patterns, agent orchestration patterns, quality gate strategies, error recovery approaches. Check .factory/archive/ for lessons from past mode creation or workflow changes. Write findings to .factory/strategy/research-practices.md covering: relevant design patterns, pitfalls to avoid, testing strategies.
Write output to: .factory/strategy/research-practices.md" --project "$PROJECT_PATH" --timeout 600 &
```

```bash
wait
```

**Important:** Run ALL commands above in a **single** Bash tool call with timeout set to at least 600 seconds.

```bash
# Artifact verification: researcher_existing
_vfail=0
_f="$PROJECT_PATH/.factory/strategy/research-existing.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: researcher_existing: .factory/strategy/research-existing.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: researcher_existing: .factory/strategy/research-existing.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=researcher_existing" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: researcher_existing artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=researcher_existing" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"

# Artifact verification: researcher_intent
_vfail=0
_f="$PROJECT_PATH/.factory/strategy/research-intent.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: researcher_intent: .factory/strategy/research-intent.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: researcher_intent: .factory/strategy/research-intent.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=researcher_intent" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: researcher_intent artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=researcher_intent" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"

# Artifact verification: researcher_practices
_vfail=0
_f="$PROJECT_PATH/.factory/strategy/research-practices.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: researcher_practices: .factory/strategy/research-practices.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: researcher_practices: .factory/strategy/research-practices.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=researcher_practices" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: researcher_practices artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=researcher_practices" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(post-barrier harness verification — DO NOT SKIP)*

## Barrier: Research

Wait for all parallel agents to complete: `researcher_existing`, `researcher_intent`, `researcher_practices`

### CEO Review — Research

Apply the CEO Review Gate protocol:
1. Read the agent output for the preceding step
2. Read artifacts: `.factory/strategy/research-existing.md`, `.factory/strategy/research-intent.md`, `.factory/strategy/research-practices.md`
3. Assess: Are the existing workflow patterns well-documented? Is the user's intent clearly structured into workflow requirements? Are best practices relevant to this type of mode? Any gaps?
4. Write verdict to `.factory/reviews/ceo-verdict-research.md`
5. **PROCEED** → continue to next step
6. **REDIRECT** → re-invoke the preceding agent with corrections (max 2)
7. **ABORT** → log failure and skip to archival

*On RELOOP: return to `fork_research` (max 3 iterations)*

## Phase 2: Strategist

```bash
factory agent strategist --task "Synthesize a workflow specification. Read ALL tagged research files at .factory/strategy/research-*.md. If the CEO task includes '## Create Mode (Update Existing Mode)', produce a change spec describing modifications to the existing workflow: which nodes/edges/prompts/gates to modify, what to add or remove, and a diff-oriented implementation plan. Include the 20-point verification checklist from the CEO task. Do NOT produce a complete new workflow definition — describe changes to the existing one. Otherwise, produce a complete specification for a new factory mode including: 1) Python code for the workflow function (nodes dict, edges list, trigger) 2) WORKFLOW_META entry (description, argument_hint) 3) CLI wiring changes (build_parser mode choices, cmd_ceo routing, _build_ceo_task section) 4) Test cases (graph validation, skill export, trigger function, registration) 5) Node details: for each node, specify id, type, role, prompt_template, reads, writes 6) Edge details: for each edge, specify source, target, condition 7) Interactive vs headless behavior Follow conventions from existing workflows — use the same patterns for builder→gate→QA→gate loops, archivist placement, and research forks. Write the specification to .factory/strategy/current.md.
Read: .factory/strategy/research-existing.md, .factory/strategy/research-intent.md, .factory/strategy/research-practices.md
Write output to: .factory/strategy/current.md" --project "$PROJECT_PATH" --timeout 600
```

```bash
# Artifact verification: strategist
_vfail=0
_f="$PROJECT_PATH/.factory/strategy/current.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: strategist: .factory/strategy/current.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: strategist: .factory/strategy/current.md is empty" && _vfail=1
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

## Phase 3: Archivist Plan

```bash
factory agent archivist --task "Archive the approved workflow specification for the new mode.
Read: .factory/strategy/current.md
Write output to: .factory/archive/create-plan.md" --project "$PROJECT_PATH" --timeout 300 --model haiku &
```
*(fire-and-forget — CEO continues immediately)*

## Phase 4: Builder

```bash
factory agent builder --task "Implement the workflow changes from the approved specification. Read the approved spec at .factory/strategy/current.md. Read CLAUDE.md for project conventions. If the CEO task includes '## Create Mode (Plugin Package)', follow the PLUGIN checklist: 1) Read **output_folder** from the CEO task 2) Create the output directory: mkdir -p <output_folder> 3) Write pyproject.toml with:    name factory-<mode-name>-workflow, version 0.1.0,    build-system hatchling, requires-python >=3.11,    dependencies [remote-factory],    entry point [factory.plugins] <mode-name> = '<mode_name>:register_plugin' 4) Write <mode_name>.py with:    meta dict (name, description),    workflow() function returning a Workflow object,    register_plugin(registry) calling registry.add_modes() and    registry.add_workflow_search_path(str(Path(__file__).parent)) 5) Write README.md with installation and usage 6) Test: pip install -e <output_folder>/ 7) Verify: factory workflow list shows the mode 8) Validate: factory workflow validate <mode-name> 9) Clean up: pip uninstall -y factory-<mode-name>-workflow The plugin package stays in the output directory — do NOT commit it to the factory repo or open a PR. It is a standalone artifact. Do NOT modify factory/workflow/definitions.py or register_all(). Otherwise, if the CEO task includes '## Create Mode (Update Existing Mode)', follow the update checklist: modify the existing workflow function in definitions.py, verify the register_all() entry still resolves, update WORKFLOW_META if needed, verify all 20 registration points from the CEO task, run factory workflow validate <name>, regenerate SKILL.md via factory workflow export-skills, update tests, run pytest and ruff check. Otherwise, follow the new-mode checklist for portable workflows: 1) Create $PROJECT_PATH/.factory/workflows/ directory if it doesn't exist 2) Write the workflow file to $PROJECT_PATH/.factory/workflows/<name>.py 3) The file must contain a `meta` dict with `name` and `description` keys, and a `workflow()` function returning a Workflow object 4) Only import from factory.workflow.primitives and stdlib — no other factory internals 5) Do NOT modify factory/workflow/definitions.py, register_all(), WORKFLOW_META, or CLI wiring — the workflow registry discovers .factory/workflows/ automatically 6) Run factory workflow validate <name> --project-path $PROJECT_PATH to verify the graph 7) Run factory workflow export-skills --project-path $PROJECT_PATH to generate the SKILL.md 8) Write tests in tests/ 9) Run pytest and ruff check to verify Commit changes and open a draft PR.
Read: .factory/strategy/current.md
Write output to: .factory/reviews/builder-latest.md" --project "$PROJECT_PATH" --timeout 1800
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

### CEO Review — Build

Apply the CEO Review Gate protocol:
1. Read the agent output for the preceding step
2. Read artifacts: `.factory/reviews/builder-latest.md`
3. Assess: Read builder output and PR diff. Does work match the approved spec? For plugin packages: verify output directory contains pyproject.toml, workflow .py with meta + workflow() + register_plugin(), and README.md. Verify NO upstream factory files were modified. For new modes: verify workflow file exists at .factory/workflows/<name>.py with meta dict and workflow() function, NOT patched into definitions.py. For existing mode updates: verify definitions.py changes are correct. Tests written. REDIRECT if any component is missing.
4. Write verdict to `.factory/reviews/ceo-verdict-build.md`
5. **PROCEED** → continue to next step
6. **REDIRECT** → re-invoke the preceding agent with corrections (max 2)
7. **ABORT** → log failure and skip to archival

*On RELOOP: return to `builder` (max 3 iterations)*

## Phase 5: Qa (Parallel)

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
factory agent adversarial_tester --task "**Plugin mode check:** If the CEO task includes '## Create Mode (Plugin Package)', verify the plugin package structure: 1) Output directory exists at the specified output_folder path. 2) pyproject.toml exists with [project.entry-points.'factory.plugins'] section. 3) Workflow .py file has meta dict + workflow() + register_plugin() function. 4) README.md documents installation and usage. 5) Run: pip install -e <folder>/ (must succeed). 6) Run: factory workflow list (must show the new mode). 7) Run: factory workflow validate <mode-name> (must pass). 8) Run: pip uninstall -y factory-<mode-name>-workflow (cleanup). Verify NO upstream factory files were modified (definitions.py, register_all, etc). **Project-local mode check:** Otherwise, for new modes: verify the workflow was written to .factory/workflows/<name>.py (NOT to definitions.py). Run: factory workflow validate <name> --project-path $PROJECT_PATH, factory workflow show <name> --project-path $PROJECT_PATH. Verify SKILL.md generated under skills/workflow-<name>/. Check workflow handles both interactive and headless paths.
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
3. Assess: Review QA results for the new mode. PROCEED if all checks pass: workflow validates, SKILL.md generated, tests pass, CLI recognizes mode. RELOOP to builder (max 3 iterations) if issues found.
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

## Phase 6: Archivist Build

```bash
factory agent archivist --task "Archive the new mode build results and learnings.
Read: .factory/reviews/adversarial-qa.md
Write output to: .factory/archive/create-build.md" --project "$PROJECT_PATH" --timeout 300 --model haiku &
```
*(fire-and-forget — CEO continues immediately)*
