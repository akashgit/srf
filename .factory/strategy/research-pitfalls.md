# Research Report — Pitfalls & MVP Scope

**Generated**: 2026-08-29  
**Target**: SRF (Scientific Research Factory) — 13 harnesses as composable factory Packages  
**Mode**: Pitfalls research for TARGETED MODE build

---

## Executive Summary

This report identifies critical pitfalls when porting 13 AI-driven scientific discovery harnesses (GEPA, OpenEvolve, AIDE, AI Scientist V2, etc.) to the factory Package ecosystem. Key risks: **fidelity loss during framework translation**, **premature abstraction**, **sandbox escape vulnerabilities**, **token budget drift**, and **MAP-Elites convergence failure**. 

**MVP Recommendation**: Start with **1 harness (GEPA)** + **3 benchmark tasks** + **shared ops layer**. Target 4-month build window, defer Lab Director to Phase 2.

---

## Potential Pitfalls to Avoid

### 1. Algorithm Porting: Fidelity vs Performance Tradeoffs

#### **Pitfall 1.1: Behavioral Fidelity Loss During Framework Translation**

**Risk**: Porting harnesses from native Python to factory Packages may silently break algorithmic behavior through:
- Island model parameter drift (migration interval, population sizes)
- Evaluation cascade timing differences (async execution in factory DAGs)
- Parent selection bias (database sampling vs in-memory structures)

**Evidence**: BenchBench (2026) found that benchmark porting pipelines "typically lack closed-loop validation of the resulting benchmarks' discriminative power, artifact resistance, modality/language fidelity, or behavioral biases" ([BenchBench, arXiv 2026](https://arxiv.org/html/2603.20807v1)).

SLUMP benchmarking showed "emergent specification consistently lowers implementation fidelity relative to a single-shot specification control, especially in structural integration" ([When the Specification Emerges, arXiv 2026](https://arxiv.org/html/2603.17104v1)).

**Mitigation**:
- **Trace-level validation**: For each ported harness, run identical tasks in Flora's version and SRF, then diff `trace.jsonl` outputs for algorithmic parity (population evolution, selection events, mutation types)
- **Behavioral regression tests**: Beyond score parity (≥95%), validate intermediate metrics (exploration/exploitation ratio, island diversity, evaluation hack rate)
- **Preserve island model parameters exactly**: Migration interval (50), migration rate (0.1), exploration/exploitation (0.3/0.7), max 5 per island, 25 total population ([Vesper harness](https://arxiv.org/html/2605.15221))

#### **Pitfall 1.2: Performance Regression from Abstraction Overhead**

**Risk**: Factory Package composition (FnNode wrapping, StateContract I/O, DAG orchestration) may add 1.3-2× latency overhead compared to native Python loops.

**Evidence**: Cross-platform porting studies show "directive-based code can reach within 1.3× of tuned baselines with mature compilers, but on some platforms trails by 1.5–2×" ([Cross-Model Portability](https://www.emergentmind.com/topics/cross-model-portability)).

**Mitigation**:
- **Cost-performance budgeting**: Track end-to-end time and token cost per experiment. If factory DAG overhead exceeds 1.5× Flora's runtime, profile bottlenecks (subprocess overhead, file I/O, Package serialization)
- **Lazy evaluation**: Use factory's conditional execution to skip expensive ops when possible (e.g., skip hack detection if score < threshold)
- **Accept 1.3× overhead as acceptable**: Don't over-optimize. Composability and tunability (OptKnobs) are more valuable than raw speed parity

#### **Pitfall 1.3: Multi-Fidelity Surrogate Model Tradeoffs**

**Risk**: When composing 13 harnesses, resist the temptation to build a "meta-model" that predicts which harness will perform best. Complex surrogates are hard to train and may not generalize.

**Evidence**: "There exists an inherent tradeoff between the expressiveness of a multi-fidelity surrogate model and the simplicity of its training process — simpler models are easier to train but have limited expressiveness" ([Multi-Fidelity Methods for Optimization, ACM 2026](https://dl.acm.org/doi/10.1145/3801959)).

**Mitigation**:
- **Defer meta-learning to Phase 3**: In Phase 1-2, treat each harness independently. Lab Director (Phase 3) can use simple heuristics (round-robin, random) rather than learned policies
- **Empirical portfolio vs surrogate**: Run all harnesses in parallel for cheap tasks, pick top-k for expensive ones based on task features (dimensionality, eval cost), not learned models

---

### 2. Over-Abstraction: Composing 13 Diverse Algorithms

#### **Pitfall 2.1: Premature Interface Unification**

**Risk**: Forcing all 13 harnesses into a uniform `Package(inputs=[Port("task")], outputs=[Port("best_solution"), Port("trace")])` may require brittle adapters that lose harness-specific affordances.

**Evidence**: Framework design research warns "too often, programmers try to come up with abstractions that are too general, and end up with something that's not composable and not simple to use" ([Towards Better Abstractions](https://blog.ploeh.dk/2010/12/03/Towardsbetterabstractions/)).

"The more members an interface has, the more difficult it is to create a Composite of it" ([Abstraction & Composition, Medium](https://medium.com/javascript-scene/abstraction-composition-cb2849d5bdd6)).

**Mitigation**:
- **Start with GEPA's natural interface**: Don't design the universal interface upfront. Implement GEPA mode first, discover its natural ports (task, initial_code?, llm_model?), then see if OpenEvolve fits the same shape
- **Allow harness-specific ports**: If AIDE needs a `literature_db` port that GEPA doesn't, that's fine. Lab Director can route different inputs to different harnesses
- **Avoid over-engineering**: 3 similar harnesses → keep interface identical. 13 diverse harnesses → allow 2-3 interface variants, not 13 custom ones

#### **Pitfall 2.2: Shared Ops Layer Becomes a Monolith**

**Risk**: The `srf/ops/` layer (code parsing, eval sandbox, budget tracking, etc.) may grow into an unmaintainable 5000-line module with 50+ functions if shared carelessly.

**Evidence**: "Heavily relying on callbacks breaks composability, and frameworks are, by design, non-composable" ([Library Patterns: Why Frameworks are Evil](https://tomasp.net/blog/2015/library-frameworks/)).

"The deployment, monitoring, and management of a large number of components separately can be complex" ([Composable Architecture](https://www.mirantis.com/blog/composable-architecture-guide/)).

**Mitigation**:
- **Fine-grained callables**: Each `FnNode.callable_name` should be a single-purpose function (50-100 lines max). Don't create `srf.ops.eval_utils:do_everything()`
- **Harness-specific ops allowed**: If GEPA's `parse_gepa_trace()` is only used by GEPA, put it in `srf/modes/gepa_ops.py`, not the shared ops layer
- **Refactor on third use**: First 2 harnesses may duplicate code. On the 3rd harness needing the same logic, extract to shared ops

#### **Pitfall 2.3: OptKnob Explosion**

**Risk**: 13 harnesses × 5-10 OptKnobs each = 65-130 tunable parameters. MAP-Elites outer loop may fail to converge in this high-dimensional space.

**Evidence**: MAP-Elites "performs a divergent search based on random mutations originating from Genetic Algorithms, and thus, is limited to evolving populations of low-dimensional solutions" ([MAP-Elites Quality-Diversity](https://www.emergentmind.com/topics/map-elites-algorithm)).

**Mitigation**:
- **Limit knobs to 3-5 per harness**: Phase 1 GEPA should expose only critical knobs (population_size, num_iterations, llm_model). Defer fine-tuning knobs (temperature, top_p) to Phase 2
- **Categorical knobs over continuous**: Use `OptKnob(bounds=["sonnet", "opus", "haiku"])` instead of `OptKnob(bounds=[0.0, 1.0])` for LLM choice. Reduces search space
- **Hierarchical knob inheritance**: Lab Director's outer loop tunes harness selection + 3 global knobs. Each harness's inner loop tunes its own 3-5 knobs independently

---

### 3. Sandbox Security: User-Submitted Code Evaluation

#### **Pitfall 3.1: Python Sandbox Escape via Object Introspection**

**Risk**: The eval sandbox (`srf/ops/eval_sandbox.py`) must execute user-generated algorithms (from GEPA, OpenEvolve, etc.). Python's dynamic nature exposes attack vectors: `__import__`, `__builtins__`, `object.__subclasses__()`, deserialization.

**Evidence**: "Maintaining a fully secure Python subset is extremely hard — Python's dynamic nature means new attack vectors appear regularly, including `__import__` abuse and object deserialization" ([Running Untrusted Python Code](https://healeycodes.com/running-untrusted-python-code)).

"Python's interconnected object system poses a fundamental challenge for sandboxing, creating critical security blind spots" ([The Glass Sandbox](https://checkmarx.com/zero-post/glass-sandbox-complexity-of-python-sandboxing/)).

**Mitigation**:
- **Use gVisor or Firecracker, not pure-Python sandboxes**: 2026 best practice is "isolation can be implemented using hardened containers, syscall interception such as gVisor, or microVM-based virtualization such as Firecracker" ([Remote Code Execution Sandbox, Northflank 2026](https://northflank.com/blog/remote-code-execution-sandbox))
- **Cloud Run Sandboxes for SRF**: If deploying as a service, use "Cloud Run Sandboxes [which] provide an isolation boundary for the main application that allows it to run potentially risky operations like running code that was user submitted or AI agent generated" ([Eval Is Evil, Google Cloud Medium](https://medium.com/google-cloud/eval-is-evil-how-to-safely-execute-untrusted-ai-code-with-cloud-run-sandboxes-and-adk-217d1737b5b7))
- **Timeout + resource limits**: 1-hour timeout per eval (same as Vesper harness), memory cap (4GB), disk quota (10GB writes), no network access
- **Evaluation hack detection**: Secondary agent validates algorithm outputs (same approach as Vesper). GEPA had 16.6% hack rate with GPT-5.2-codex ([Vesper paper](https://arxiv.org/html/2605.15221))

#### **Pitfall 3.2: Filesystem Race Conditions in Parallel Evaluation**

**Risk**: Running multiple harness instances in parallel on a shared filesystem risks file conflicts if they write to the same paths (`best_solution.py`, `trace.jsonl`).

**Evidence**: Vesper harness identified "running multiple search agents in parallel on a shared filesystem risks file conflicts and race conditions" ([Vesper paper](https://arxiv.org/html/2605.15221)).

**Mitigation**:
- **Git worktrees for isolation**: "Git worktrees provide complete filesystem isolation without cloning the entire repository — achieving 3.2-3.9× parallelism speedup" (Vesper)
- **Factory worktree support**: SRF is running in a factory worktree (`run-784c3db9`), so parallel agents can use nested worktrees or temporary directories
- **Unique output paths**: Each Package run writes to `outputs/{run_id}/best_solution.py`, not a shared location

#### **Pitfall 3.3: Dependency Confusion in Eval Environment**

**Risk**: User-generated algorithms may import packages not in SRF's venv, causing eval failures. Or worse, import malicious packages with typosquatting names.

**Mitigation**:
- **Allowlist imports**: Eval sandbox should only allow `numpy`, `scipy`, `matplotlib` (per task requirements). Block all other imports
- **Vendored dependencies**: For tasks requiring specific versions (e.g., `autocorrelation_inequality` needs `scipy==1.10.0`), vendor them in `srf/tasks/*/vendor/`
- **Fail fast on missing imports**: If algorithm tries `import torch`, eval should immediately return score=0 with error message, not silently fail

---

### 4. Budget Tracking Accuracy: LLM Token Counting

#### **Pitfall 4.1: Client-Side Estimates Diverge from Billing**

**Risk**: If SRF's budget tracker uses string length or tiktoken estimates instead of actual API-returned token counts, cost tracking will drift from invoice reality.

**Evidence**: "The total_cost_usd and costUSD fields are client-side estimates, not authoritative billing data. The SDK computes them locally from a price table bundled at build time" ([Track Cost and Usage, Claude Code Docs](https://code.claude.com/docs/en/agent-sdk/cost-tracking)).

"Don't estimate from message length alone — let the API tell you what it actually counted" ([Token Counting, Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/token-counting)).

**Mitigation**:
- **Ingest API-returned counts**: Every LLMNode invocation must parse `usage.input_tokens` and `usage.output_tokens` from the API response and store them in `trace.jsonl`
- **Update estimates from real responses**: "Estimation is useful for pre-flight checks, but always update your tracked count from real API responses" (Claude docs)
- **Account for prompt caching**: "For accurate cost tracking, account for the placeholder output count on assistant messages, the tokens a failed conversation consumed, and cache token pricing" (Claude Code docs)

#### **Pitfall 4.2: Token Count Inflation with Nested Agents**

**Risk**: Multi-agent harnesses (e.g., Vesper's parent selection → agent execution → hack detection) may undercount total tokens if only tracking the main agent's usage.

**Evidence**: "Anthropic's engineering team measured it directly: 'agents typically use about 4× more tokens than chat interactions, and multi-agent systems use about 15× more tokens than chats'" ([AI Coding Costs 2026](https://www.morphllm.com/ai-coding-costs)).

"Use modelUsage, or model_usage in Python, for whole-tree token accounting; the usage field undercounts as soon as nesting occurs" (Claude Code docs).

**Mitigation**:
- **Whole-tree accounting**: If GEPA spawns sub-agents (reflection agent, mutation agent), accumulate their token counts into the parent's budget
- **Budget gates**: Each Package should check `current_tokens < budget_limit` before spawning LLMNodes. Fail early if budget exhausted
- **Cost parity validation**: Compare SRF's total token usage to Flora's baselines. If GEPA uses >2× Flora's tokens for same score, investigate architectural overhead

#### **Pitfall 4.3: Tokenizer Version Drift**

**Risk**: Claude Opus 4.7's tokenizer (April 2026) counts more tokens for the same text than prior models. If SRF targets GPT-5 but cost estimates use GPT-4 rates, budget blowout.

**Evidence**: "Claude token spend got harder to predict in 2026, not easier. The Claude Opus 4.7 tokenizer that shipped in April counts more tokens for the same text than the models before it" ([AI Coding Costs 2026](https://www.morphllm.com/ai-coding-costs)).

**Mitigation**:
- **Model-specific cost tables**: Maintain separate token→cost mappings per LLM provider and version
- **Budget headroom**: Set budget limits to 80% of theoretical max to absorb tokenizer variance
- **Fail gracefully on budget overrun**: If experiment exceeds budget mid-run, log partial results to `trace.jsonl` rather than crashing

---

### 5. MAP-Elites Outer Loop: Convergence Issues

#### **Pitfall 5.1: Premature Convergence to Local Optima**

**Risk**: The Lab Director's outer loop (Phase 3) uses MAP-Elites to evolve harness configurations (which harness, which OptKnobs). MAP-Elites may converge to one good config early and stop exploring.

**Evidence**: "Search algorithms still tend to converge to one or a few good solutions early and cease to make further progress" ([MAP-Elites Quality-Diversity](https://www.emergentmind.com/topics/map-elites-algorithm)).

"The SHINE algorithm and Novelty search both outperform MAP-Elites because of the deceptive nature of the fitness objective used in the cells of MAP-Elites" ([Quality-Diversity Algorithms](https://towardsdatascience.com/quality-diversity-algorithms-a-new-approach-based-on-map-elites-applied-to-robot-navigation-f51380deec5d/)).

**Mitigation**:
- **Multi-Emitter MAP-Elites**: Use ME-MAP-Elites variant with heterogeneous mutation operators (random, gradient-based, crossover) to maintain diversity ([Multi-Emitter MAP-Elites, arXiv 2020](https://arxiv.org/abs/2007.05352))
- **Diversity metrics in feature space**: Archive configurations by (task_type, harness_family) dimensions, not just (score, cost)
- **Periodic restarts**: Every 50 iterations, inject random configs to escape local optima

#### **Pitfall 5.2: Deceptive Fitness Objectives**

**Risk**: If the outer loop optimizes only for `final_score`, it may select configs that overfit to eval hacks or cheap tasks.

**Evidence**: "CMA-ME suffers from three major limitations: prematurely abandoning the objective in favor of exploration, struggling to explore flat objectives, and having poor performance for low-resolution archives" ([MAP-Elites with Descriptor-Conditioned Gradients](https://arxiv.org/abs/2303.03832)).

**Mitigation**:
- **Multi-objective fitness**: Optimize (score, cost, diversity, robustness) simultaneously. Pareto frontier, not single scalar
- **Validation set**: Hold out 20% of tasks. Outer loop optimizes on training tasks, selects configs by validation performance
- **Hack detection**: Run Vesper-style secondary validation on top-scoring configs. Discard configs with >10% hack rate

#### **Pitfall 5.3: Gradient-Free Optimization in High Dimensions**

**Risk**: MAP-Elites uses random mutations. With 65-130 OptKnobs across 13 harnesses, search space is too large for random walk.

**Evidence**: "MAP-Elites relies on random variations that can cause slow convergence in large search spaces, making it inadequate to evolve neural networks with a large number of parameters" ([Quality-Diversity Algorithms](https://towardsdatascience.com/quality-diversity-algorithms-a-new-approach-based-on-map-elites-applied-to-robot-navigation-f51380deec5d/)).

"PGA-MAP-Elites fails on several tasks where the convergent search of the gradient-based operator does not direct mutations towards archive-improving solutions" ([MAP-Elites with Descriptor-Conditioned Gradients](https://arxiv.org/abs/2303.03832)).

**Mitigation**:
- **Descriptor-conditioned gradients**: If using continuous OptKnobs (temperature, population_size), compute gradient estimates via finite differences on successful runs
- **Limit knob dimensionality**: See Pitfall 2.3 — keep to 3-5 knobs per harness, categorical when possible
- **CMA-ES for continuous knobs**: Hybrid approach: MAP-Elites for discrete harness selection, CMA-ES for continuous knob tuning within each harness

---

### 6. Additional Cross-Cutting Pitfalls

#### **Pitfall 6.1: Knowledge Loss Between Iterations**

**Risk**: Stateless harnesses regenerate code from scratch each iteration without learning from past failures.

**Evidence**: Vesper paper identified "each iteration starts from a blank slate, without systematically leveraging knowledge of successes and failures" as a key limitation of prior harnesses ([Vesper](https://arxiv.org/html/2605.15221)).

**Mitigation**:
- **Reflective memory**: Store algorithm descriptions, improvement ideas, and rationale in database (SQLite or MemPalace)
- **Agent access to history**: LLMNodes receive `context=past_attempts` as input, allowing them to build on prior work
- **Incremental evolution**: Each generation mutates the best from prior generation, not random restart

#### **Pitfall 6.2: Evaluation Hacking**

**Risk**: Generated algorithms may exploit flaws in `eval.py` to achieve high scores without solving the task (e.g., hardcoding expected output, reading test data).

**Evidence**: "More capable models produced evaluation hacks at higher rates: 16.6% hack rate for GPT-5.2-codex vs 0% for GPT-5.1-codex-mini" (Vesper).

**Mitigation**:
- **Held-out test cases**: `eval.py` validates on unseen inputs not shown to the LLM
- **Secondary validation agent**: After each high-scoring algorithm, a separate LLM reviews code for suspicious patterns (hardcoding, file reads)
- **Trace analysis**: Check `trace.jsonl` for anomalies (sudden score jumps, identical outputs across diverse inputs)

#### **Pitfall 6.3: Over-Reliance on Expensive Models**

**Risk**: Assuming GPT-5.2-codex is always best may blow budget. But cheaper models (Sonnet, GPT-5.1-mini) can match performance on some tasks.

**Evidence**: "Expensive models offer better cost-performance than inexpensive models" on average, but Vesper found GPT-5.1-codex-mini achieved 0% hack rate vs 16.6% for GPT-5.2 (Vesper).

"CodeEvolve achieves superior performance on several tasks and competitive results overall, enabling open-weight models to match or exceed the performance of closed-source baselines at a fraction of the compute cost" ([CodeEvolve, arXiv 2025](https://arxiv.org/html/2510.14150v4)).

**Mitigation**:
- **Model selection as OptKnob**: Let outer loop tune `llm_model` per task. Some tasks may prefer Sonnet (cheap, deterministic) over Opus (expensive, creative)
- **Cascading model calls**: Start with Haiku for initial exploration, escalate to Sonnet/Opus only if score plateaus
- **Budget-aware scheduling**: Allocate 70% of token budget to top 3 harnesses, 30% to exploratory runs with cheaper models

---

## MVP Scope Recommendation

### Context: Phase 1 Plan vs MVP Best Practices

**Phase 1 from factory.md**:
1. Repo scaffolding (pyproject.toml, CLI, registries)
2. Common infrastructure (eval sandbox, budget tracking, tracing, code parsing)
3. GEPA mode (Package + ops)
4. Port 3 tasks (circle_packing, autocorrelation_inequality, trimul)
5. Test GEPA (graph validation, e2e)
6. Validate (score parity ≥95%, cost parity)

**MVP best practices**: "A well-scoped MVP typically includes 3-5 core features that solve the primary problem. If your timeline exceeds 4 months, you're likely building too much" ([MVP Scope, Lemberg Solutions](https://lembergsolutions.com/blog/mvp-scope-how-define-your-minimum-viable-product-4-steps)).

"Simple MVPs with 3-5 features can be built in 6-8 weeks, while more complex products requiring custom infrastructure may take 12-16 weeks" ([MVP Roadmap Guide 2026](https://wearepresta.com/the-complete-mvp-roadmap-guide-for-2026/)).

### Recommended MVP Scope (4-Month Build)

**Phase 1 — GEPA Foundation (Weeks 1-8)**

✅ **Keep from original plan**:
- Repo scaffolding (pyproject.toml, `srf` package, CLI entry points)
- GEPA mode Package definition (`srf/modes/gepa.py`)
- 3 benchmark tasks (circle_packing, autocorrelation_inequality, trimul)
- Eval sandbox with gVisor isolation
- Budget tracking (API token ingestion)
- Basic tracing (actions, scores, costs to JSONL)
- E2E test: GEPA on circle_packing

🔄 **Simplify from original plan**:
- **Defer advanced tracing**: Phase 1 traces only (action, timestamp, score, cost). Skip algorithm descriptions, improvement ideas, rationale — those require reflective memory (Pitfall 6.1), defer to Phase 2
- **No hack detection yet**: Vesper's secondary validation agent is Phase 2 work. Phase 1 just logs suspicious scores (>2σ jumps) for manual review
- **No graph validation**: Factory graph update is useful but not MVP-blocking. Defer to Phase 2
- **Code parsing via AST only**: No advanced static analysis. Just extract function signatures and imports

❌ **Explicitly out of scope for MVP**:
- Lab Director (Phase 3)
- Multi-harness comparison (need ≥2 harnesses for this, MVP has 1)
- Outer loop OptKnob tuning (need Lab Director first)
- Reflective memory database (Pitfall 6.1 mitigation — Phase 2)
- Hack detection agent (Pitfall 6.2 mitigation — Phase 2)

**Success Criteria (Phase 1 Gate)**:
1. ✅ GEPA mode runs on circle_packing task
2. ✅ Score ≥95% of Flora's GEPA baseline (e.g., if Flora = 2.636, SRF ≥2.504)
3. ✅ Cost ≤150% of Flora's token usage (1.5× overhead acceptable, see Pitfall 1.2)
4. ✅ Trace diff shows behavioral parity (same island populations, migration events)
5. ✅ Eval sandbox contains gVisor or similar isolation
6. ✅ Budget tracker logs API-returned token counts, not estimates

**Phase 2 — Second Harness + Robustness (Weeks 9-16)**

✅ **Add second harness**:
- OpenEvolve mode (`srf/modes/open_evolve.py`)
- Reuse GEPA's ops layer where possible, extract shared code to `srf/ops/`
- Test on same 3 tasks, compare performance to GEPA

✅ **Robustness features** (mitigations from pitfalls):
- Reflective memory database (SQLite, store algorithm descriptions + rationale)
- Hack detection agent (secondary validation)
- Multi-objective fitness tracking (score, cost, diversity)
- Advanced tracing (capture improvement ideas)

✅ **Infrastructure hardening**:
- Graph validation (factory graph update integration)
- Parallel execution (Git worktrees, up to 4 concurrent agents)
- Model selection as OptKnob (Sonnet/Opus/Haiku)

**Success Criteria (Phase 2 Gate)**:
1. ✅ Two harnesses (GEPA + OpenEvolve) validated on 3 tasks
2. ✅ Hack detection catches ≥80% of known exploit patterns
3. ✅ Shared ops layer has <20% code duplication between harnesses
4. ✅ Parallel execution achieves ≥3× speedup on 4-core machine

**Phase 3 — Lab Director (Out of MVP, Future Work)**

🔮 **Deferred to post-MVP**:
- Lab Director agent (`srf/lab/director.py`)
- MAP-Elites outer loop for harness selection
- Multi-harness portfolio optimization
- Remaining 11 harnesses (AIDE, AI Scientist V2, etc.)

### Timeline Estimate

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 (MVP) | 8 weeks | GEPA mode + 3 tasks + eval sandbox + budget tracking |
| Phase 2 (Robust) | 8 weeks | OpenEvolve mode + hack detection + reflective memory |
| **Total for 2-harness system** | **16 weeks (4 months)** | Production-ready SRF with 2 validated harnesses |
| Phase 3 (Lab Director) | 8 weeks | Multi-harness orchestration + outer loop |
| Phase 4 (Scale) | 12 weeks | Remaining 11 harnesses |

**Critical Path**: Eval sandbox security is on critical path. If gVisor setup takes >2 weeks, consider using Cloud Run Sandboxes or Firecracker to unblock progress.

**Risk Buffer**: Add 2-week buffer to Phase 1 for unexpected issues (sandbox setup, token budget API changes, trace diff debugging).

---

## Lessons from Similar Past Builds

### From Archive
No prior SRF-specific builds in `.factory/archive/`. This is a greenfield project.

### From External Research

#### **Lesson 1: Agent Autonomy > Stateless Generation** (Vesper 2026)

**Finding**: "Scaling reasoning per algorithm is more effective than scaling the number of generations under fixed budgets. Investing more tokens per iteration to produce fewer high-quality candidates via coding agents proved more efficient than generating many low-quality candidates through cheap API calls" ([Vesper](https://arxiv.org/html/2605.15221)).

**Application to SRF**: 
- Each LLMNode should be a multi-step agent (repository reading, test execution, debugging) rather than a single prompt→code call
- Better to run 10 iterations with Opus doing deep reasoning than 100 iterations with Haiku doing shallow generation
- Budget 1-hour timeout per agent session (same as Vesper)

#### **Lesson 2: Evaluation Cascades for Efficiency** (Vesper 2026)

**Finding**: Vesper uses "multiple threshold levels for efficiency — cheap evals filter obvious failures before running expensive full validation".

**Application to SRF**:
- `eval.py` should have fast path (syntax check, basic smoke test, <1 sec) and slow path (full test suite, 30-60 sec)
- Only run slow path if fast path passes
- Save 80%+ of eval budget by failing fast on broken code

#### **Lesson 3: Closed-Loop Fidelity Validation** (BenchBench 2026)

**Finding**: "Benchmark porting pipelines typically lack closed-loop validation of discriminative power, artifact resistance, and behavioral biases across diverse models" ([BenchBench](https://arxiv.org/html/2603.20807v1)).

**Application to SRF**:
- Don't just compare final scores (GEPA: 2.636 vs 2.504). Validate intermediate behaviors:
  - Island population diversity over time
  - Parent selection distribution (uniform? biased toward elites?)
  - Mutation type frequency (crossover vs random vs gradient)
- Build "behavioral regression suite" that diffs trace outputs, not just scores

#### **Lesson 4: Git Worktrees for Parallelism** (Vesper 2026)

**Finding**: "Git worktrees provide complete filesystem isolation without cloning the entire repository — achieving 3.2-3.9× parallelism speedup" (Vesper).

**Application to SRF**:
- Phase 2 should use factory's worktree support to run 4 harness instances in parallel
- Each worktree gets its own `outputs/{run_id}/` directory, no shared state
- Expect 3× speedup on 4-core machines (3.2-3.9× range)

#### **Lesson 5: Multi-Emitter MAP-Elites for Robustness** (Cully et al. 2020)

**Finding**: "Multi-Emitter MAP-Elites improves quality, diversity and convergence speed with heterogeneous sets of emitters" ([ME-MAP-Elites, arXiv 2020](https://arxiv.org/abs/2007.05352)).

**Application to SRF**:
- When building Lab Director (Phase 3), use ME-MAP-Elites with 3+ emitters:
  1. Random emitter (exploration)
  2. Gradient-based emitter (exploitation of continuous knobs)
  3. Crossover emitter (recombination of successful configs)
- Don't use vanilla MAP-Elites — it's known to converge poorly (Pitfall 5.1)

#### **Lesson 6: Model Cost-Performance is Non-Linear** (Vesper 2026, CodeEvolve 2025)

**Finding**: "Expensive models offer better cost-performance than inexpensive models on average, but GPT-5.1-codex-mini achieved 0% hack rate vs 16.6% for GPT-5.2-codex" (Vesper).

"Open-weight models can match or exceed the performance of closed-source baselines at a fraction of the compute cost" ([CodeEvolve](https://arxiv.org/html/2510.14150v4)).

**Application to SRF**:
- Don't hardcode Opus for everything. Make `llm_model` an OptKnob
- For hack detection, use cheaper model (Sonnet or Haiku) — it's more conservative
- For mutation generation, use expensive model (Opus) — creativity matters
- Validate cost-performance empirically on SRF's tasks, don't assume GPT-5.2 > Sonnet

#### **Lesson 7: Synthetic Fidelity–Stability Framework** (SFSF 2026)

**Finding**: SFSF benchmark showed "the need to balance statistical realism, dependency preservation, privacy risk, and robustness to seed and output scale" when evaluating synthetic data generators ([SFSF, bioRxiv 2026](https://www.biorxiv.org/content/10.64898/2026.08.11.741471v1.full)).

**Application to SRF**:
- When validating SRF vs Flora baselines, don't just check score parity. Also validate:
  - **Statistical realism**: Are output distributions similar? (KL divergence, Wasserstein distance)
  - **Dependency preservation**: Do algorithm components interact the same way? (correlation structure)
  - **Robustness to seed**: Run 5× with different random seeds, check variance
  - **Output scale stability**: Does performance degrade on 10× larger tasks?

---

## References

### Algorithm Porting & Fidelity
- [Cross-Model Portability](https://www.emergentmind.com/topics/cross-model-portability) — Framework porting tradeoffs
- [Multi-Fidelity Methods for Optimization](https://dl.acm.org/doi/10.1145/3801959) — ACM survey on fidelity tradeoffs
- [BenchBench: Benchmarking Automated Benchmark Generation](https://arxiv.org/html/2603.20807v1) — Closed-loop validation (2026)
- [When the Specification Emerges](https://arxiv.org/html/2603.17104v1) — Faithfulness loss in long-horizon coding (2026)
- [Synthetic Fidelity–Stability Framework](https://www.biorxiv.org/content/10.64898/2026.08.11.741471v1.full) — Multi-criterion fidelity benchmarking (2026)

### Composable Framework Design
- [Towards Better Abstractions](https://blog.ploeh.dk/2010/12/03/Towardsbetterabstractions/) — Over-abstraction pitfalls
- [Composable Abstractions in Practice](https://mb21.github.io/blog/2021/09/11/composable-abstractions) — Design patterns
- [Library Patterns: Why Frameworks are Evil](https://tomasp.net/blog/2015/library-frameworks/) — Composability challenges
- [Abstraction & Composition](https://medium.com/javascript-scene/abstraction-composition-cb2849d5bdd6) — Interface design principles
- [Composable Architecture Guide](https://www.mirantis.com/blog/composable-architecture-guide/) — Deployment complexity

### Sandbox Security
- [The Glass Sandbox](https://checkmarx.com/zero-post/glass-sandbox-complexity-of-python-sandboxing/) — Python sandboxing challenges
- [Remote Code Execution Sandbox](https://northflank.com/blog/remote-code-execution-sandbox) — 2026 isolation guide
- [Running Untrusted Python Code](https://healeycodes.com/running-untrusted-python-code) — Security best practices
- [Eval Is Evil](https://medium.com/google-cloud/eval-is-evil-how-to-safely-execute-untrusted-ai-code-with-cloud-run-sandboxes-and-adk-217d1737b5b7) — Cloud Run Sandboxes (2026)
- [Effective Harness Engineering](https://arxiv.org/html/2605.15221) — Vesper paper on eval hacking and filesystem isolation (2026)

### LLM Budget Tracking
- [Track Cost and Usage](https://code.claude.com/docs/en/agent-sdk/cost-tracking) — Claude Code cost tracking
- [Token Counting](https://platform.claude.com/docs/en/build-with-claude/token-counting) — Claude API token counting
- [AI Coding Costs (2026)](https://www.morphllm.com/ai-coding-costs) — Multi-agent token usage patterns

### MAP-Elites & Quality-Diversity
- [MAP-Elites Algorithm](https://www.emergentmind.com/topics/map-elites-algorithm) — Overview and convergence issues
- [Quality-Diversity Algorithms](https://towardsdatascience.com/quality-diversity-algorithms-a-new-approach-based-on-map-elites-applied-to-robot-navigation-f51380deec5d/) — Applied examples
- [Multi-Emitter MAP-Elites](https://arxiv.org/abs/2007.05352) — ME-MAP-Elites for improved convergence (2020)
- [MAP-Elites with Descriptor-Conditioned Gradients](https://arxiv.org/abs/2303.03832) — Gradient-based improvements (2023)

### MVP Scope & Best Practices
- [MVP Scope Definition](https://lembergsolutions.com/blog/mvp-scope-how-define-your-minimum-viable-product-4-steps) — 4-step framework
- [MVP Roadmap Guide 2026](https://wearepresta.com/the-complete-mvp-roadmap-guide-for-2026/) — Timeline best practices
- [MVP Explained](https://ieeexplore.ieee.org/document/7592786/) — Systematic mapping study
- [MVP Development Strategy](https://fullscale.io/blog/mvp-development-strategy/) — Why cutting scope beats process

### Harness Implementation & Benchmarking
- [Effective Harness Engineering](https://arxiv.org/html/2605.15221) — Vesper harness design (2026)
- [GEPA: Reflective Prompt Evolution](https://arxiv.org/pdf/2507.19457) — ICLR 2026 Oral
- [CodeEvolve](https://arxiv.org/html/2510.14150v4) — Open-source evolutionary framework (2025)
- [AI-Driven Research at Berkeley](https://ucbskyadrs.github.io/blog/berkeley-ai-driven-research/) — ADRS benchmark results

---

**Status**: Research complete. Ready for Strategist to consume these findings and generate hypothesis for GEPA mode + 3 tasks build.
