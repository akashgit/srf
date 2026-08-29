# Researcher Agent Output

- **timestamp:** 2026-08-29T18:58:37Z
- **exit_code:** 0

---

Research complete. I've written a comprehensive analysis of similar projects to `.factory/strategy/research-similar.md`.

## Summary

**8 similar projects analyzed**:

1. **Harness-Bench** — Shows harness design creates 23.8-point performance variance; validates SRF's composable approach
2. **OpenEvolve** — Open-source evolutionary coding with MAP-Elites; demonstrates feasibility of outer loops
3. **AIDE** — Tree search in code space; outperformed top AI scientists from DeepMind/Google within 6 hours
4. **AI Scientist v2** — First peer-reviewed AI-generated paper; uses agentic tree search manager
5. **FunSearch** — DeepMind's foundational work; achieved 20-year breakthrough on cap set problem
6. **ResearchClawBench** — The actual benchmark for autonomous research (40 tasks, 10 domains); current best score is 21.5/100
7. **LLM Program Synthesis Benchmarks** — 2026 landscape shows 84-89% on synthetic but only 25-34% on real-world tasks
8. **Harness Engineering Ecosystem** — Emerging field; harness changes alone yielded 52.8% → 66.5% improvement

**Key differentiation**: Existing tools are either execution platforms (run one harness) or single-strategy agents. SRF is a **harness discovery platform** — comparing and evolving 13 strategies with tunable OptKnobs.

**Top recommendations**:
- Harness interface standardization (uniform Ports across 13 modes)
- Evolutionary outer loop using AIDE's tree search + MAP-Elites
- Eval sandbox isolation (cost tracking, resource limits)
- Start with circle_packing task (OpenEvolve achieved SOTA at 2.634)
---

> **⚠ CEO IDENTITY RE-ANCHOR (Sacred Rule 8)**
> You are the Factory CEO. You orchestrate, delegate, and decide. You do NOT implement.
> If you are about to write code, run tests, do research, or fix bugs — STOP and spawn the appropriate agent.
> Re-read your Permitted/Forbidden Actions lists in the Identity section above.
