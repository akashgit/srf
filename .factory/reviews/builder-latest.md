# Builder Review — Documentation

**Date:** 2026-08-30
**Task:** Write comprehensive documentation for SRF

## Changes

- Created `docs/USER_GUIDE.md` — complete user-facing documentation covering installation, quick start, all 6 CLI subcommands with flags and examples, all 13 modes organized by strategy family, task creation (task.yaml schema, eval.py contract, initial.py), provider setup for all 4 providers, environment variables reference, output format and files, sandbox backends, and hack detection
- Created `docs/DEVELOPER_GUIDE.md` — complete developer documentation covering step-by-step mode creation (with code examples from existing modes), mode registration auto-discovery, all 13 DAG primitives with signatures and usage examples, FnNode callable_name wiring, OptKnobs system, MemoryDeclarations, shared ops in ops/common/, task and eval creation, adding LLM providers, adding sandbox backends, hack detection internals, telemetry integration, Lab Director protocol and multi-mode orchestration, MAP-Elites grid structure and evolution loop, and testing

## Evidence Sources

All content backed by three evidence files:
- `.factory/strategy/doc-evidence-modes.md` — mode template, registration, DAG primitives, knobs, memory
- `.factory/strategy/doc-evidence-infra.md` — tasks, eval, sandbox, providers, telemetry, hack detection, Lab Director, MAP-Elites
- `.factory/strategy/doc-evidence-cli.md` — CLI entry point, subcommands, flags, env vars, output format

## Verification

- All file paths verified against filesystem (srf/modes/, srf/ops/, srf/tasks/, srf/lab/, srf/telemetry/)
- All 13 mode files confirmed present
- All task directories confirmed present
- Uses `uv` everywhere (never `pip`)
- Every code snippet sourced from evidence files with line numbers
- Every function signature matches evidence
- No invented features or APIs
