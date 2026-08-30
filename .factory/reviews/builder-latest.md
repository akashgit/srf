# Builder Review — README.md Rewrite

## Changes

- Rewrote README.md to document all 13 implemented modes (was only covering GEPA)
- Added Quick Start section with `uv pip install` and `srf` CLI entry point
- Added full modes table with strategy description and use-case guidance for all 13 modes
- Added CLI Reference covering all 6 subcommands: `run`, `modes`, `tasks`, `lab`, `evolve`, `validate`
- Added Lab Director section with example command for comparing modes
- Added MAP-Elites section with example command and flag table
- Added task.yaml schema with `reference_score` field and `srf validate` workflow
- Expanded architecture table to cover all layers (lab director, MAP-Elites, tracing, budget, hack detection, telemetry, memory)
- Added Provider Setup table with install commands and required env vars
- Removed "Planned Modes" section (all modes are now implemented)

## Status

Complete. README covers all features, is concise (~160 lines), and can be read in under 5 minutes.
