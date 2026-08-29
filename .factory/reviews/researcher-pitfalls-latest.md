# Researcher Agent Output

- **timestamp:** 2026-08-29T19:00:00Z
- **exit_code:** 0

---

Research complete. I've written a comprehensive pitfalls and MVP scope report to `.factory/strategy/research-pitfalls.md` covering:

## Key Findings

**Critical Pitfalls Identified**:
1. **Fidelity loss during framework porting** — Trace-level validation needed, not just score parity
2. **Over-abstraction risk** — Start with GEPA's natural interface, allow 2-3 variants (not 13 custom ones)
3. **Sandbox escapes** — Use gVisor/Firecracker, not pure-Python sandboxes (16.6% eval hack rate with GPT-5.2)
4. **Token budget drift** — Ingest API-returned counts; multi-agent systems use 15× more tokens than expected
5. **MAP-Elites premature convergence** — Use Multi-Emitter variant with heterogeneous mutation operators

**MVP Scope (4-Month Build)**:
- Phase 1 (8 weeks): GEPA mode + 3 tasks + eval sandbox + budget tracking
- Phase 2 (8 weeks): OpenEvolve mode + hack detection + reflective memory
- Success criteria: ≥95% score parity, ≤150% cost overhead, behavioral trace alignment

**Key Lessons from 2026 Research**:
- Agent autonomy > stateless generation (Vesper: invest more tokens per iteration, not more iterations)
- Git worktrees achieve 3.2-3.9× parallelism speedup
- Closed-loop validation required — check intermediate behaviors, not just final scores
- Model cost-performance is non-linear — make `llm_model` an OptKnob

Report includes 25+ sources with actionable mitigations for each risk area.
---

> **⚠ CEO IDENTITY RE-ANCHOR (Sacred Rule 8)**
> You are the Factory CEO. You orchestrate, delegate, and decide. You do NOT implement.
> If you are about to write code, run tests, do research, or fix bugs — STOP and spawn the appropriate agent.
> Re-read your Permitted/Forbidden Actions lists in the Identity section above.
