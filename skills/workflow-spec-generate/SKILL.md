---
name: workflow-spec-generate
description: "Run the spec-generate workflow."
disable-model-invocation: true
argument-hint: "<project_path>"
---

# Spec Generate Workflow

The user wants: **$ARGUMENTS**

## Step: Extract

Run graphify to extract a code knowledge graph from the project source.

```bash
factory graph extract $PROJECT_PATH
```

### CEO Review — Extract

Apply the CEO Review Gate protocol:
1. Read the agent output for the preceding step
2. Read artifacts: `graph.json`
3. Assess: Check that graph.json was produced. Verify it contains nodes and edges. PROCEED if the graph was extracted successfully. RELOOP if missing or empty.
4. Write verdict to `.factory/reviews/ceo-verdict-extract.md`
5. **PROCEED** → continue to next step
6. **REDIRECT** → re-invoke the preceding agent with corrections (max 2)
7. **ABORT** → log failure and skip to archival

*On RELOOP: return to `extract` (max 3 iterations)*

## Phase 1: Researcher — Annotate

```bash
factory agent researcher --task "Read the code knowledge graph at graph.json. Read the spec_annotator prompt at factory/agents/prompts/spec_annotator.md. Produce a two-tier behavioral spec with RFC 2119 normative language. Use [[graph:...]] reference links for granular module details. Write output to SPEC.md in the project root.
Read: graph.json
Write output to: SPEC.md" --project "$PROJECT_PATH" --timeout 600
```

```bash
# Artifact verification: annotate
_vfail=0
_f="$PROJECT_PATH/SPEC.md"
[ ! -f "$_f" ] && echo "VERIFY FAIL: annotate: SPEC.md missing" && _vfail=1
[ -f "$_f" ] && [ ! -s "$_f" ] && echo "VERIFY FAIL: annotate: SPEC.md is empty" && _vfail=1
[ "$_vfail" -ne 0 ] && echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_FAIL node=annotate" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt" && exit 1
echo "VERIFY OK: annotate artifacts validated"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) VERIFY_OK node=annotate" >> "$PROJECT_PATH/.factory/hooks/hook-log.txt"
```
*(harness verification — DO NOT SKIP)*

### CEO Review — Annotate

Apply the CEO Review Gate protocol:
1. Read the agent output for the preceding step
2. Read artifacts: `SPEC.md`
3. Assess: Review the annotated spec at SPEC.md. Check: do module behavioral contracts match the actual code? Does the spec use RFC 2119 normative language (MUST/SHOULD/MAY)? Are there scoring tables (there should NOT be)? SECTION COMPLETENESS CHECK — verify ALL of the following sections are present and non-empty:  Problem Statement,  Goals and Non-Goals (including.1 Goals.2 Non-Goals.3 Design Philosophy),  Project Identity,  Technical Stack,  Architecture Overview,  Domain Model,  State Machines and Lifecycles,  Module Specifications,  Shared Contracts,  Configuration Specification,  Entry Points,  Failure Model and Recovery,  Security and Safety,  Test and Validation Matrix,  Extension Points,  Implementation Checklist, Appendix A: Reference Algorithms. RELOOP if ANY section is missing or empty. PROCEED only if ALL 16 sections + Appendix A are present and non-empty.
4. Write verdict to `.factory/reviews/ceo-verdict-annotate.md`
5. **PROCEED** → continue to next step
6. **REDIRECT** → re-invoke the preceding agent with corrections (max 2)
7. **ABORT** → log failure and skip to archival

*On RELOOP: return to `annotate` (max 3 iterations)*

## Step: Validate

Run automated consistency checks on the annotated SPEC.md. Must run after annotation is CEO-approved.

```bash
factory spec validate $PROJECT_PATH
```

### CEO Review — Validate

Apply the CEO Review Gate protocol:
1. Read the agent output for the preceding step
2. Read artifacts: `SPEC.md`
3. Assess: Final quality gate for the repo spec. Read SPEC.md. Is it complete, well-structured, and under 24K tokens? PROCEED to finish.
4. Write verdict to `.factory/reviews/ceo-verdict-validate.md`
5. **PROCEED** → continue to next step
6. **REDIRECT** → re-invoke the preceding agent with corrections (max 2)
7. **ABORT** → log failure and skip to archival
