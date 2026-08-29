# Research Report — Similar Projects

**Generated**: 2026-08-29  
**Focus**: AI-driven scientific discovery frameworks, evolutionary code optimization, LLM program synthesis benchmarks, harness comparison

---

## Project Summary

**SRF (Scientific Research Factory)** reimplements 13 AI-driven scientific discovery harnesses (from the harness-comparison benchmark landscape) as composable factory workflow Packages on top of remote-factory's Package ecosystem. The goal is to create a unified framework where a single research question can be refracted through multiple strategies, each with tunable OptKnobs that an outer evolutionary loop can optimize.

**Current state**: Initial scaffolding complete with eval infrastructure and workflow skills. Phase 1 focus is implementing GEPA mode (Genetic Programming with LLM Evaluation and Automated Selection) with 3 benchmark tasks.

---

## External Research Findings

### 1. Harness-Bench: Measurement Framework for Harness Design

**Source**: [Harness-Bench paper](https://arxiv.org/html/2605.27922v1)

**What it is**: A benchmark evaluating 6 configurable agent harnesses (OpenClaw, ZeroClaw, Hermes, Moltis, NullClaw, NanoBot) across 8 model backends on 106 sandboxed tasks, producing 5,194 execution trajectories.

**Key findings**:
- **Performance variation**: Harness design creates a 23.8-point performance gap (52.4% to 76.2%) using identical tasks and models
- **Agent = Model + Harness**: Performance must be reported at configuration level, not model alone
- **Execution alignment**: Critical concept measuring "correspondence among reasoning, workspace state, tool actions, and evaluator conditions"
- **Failure modes**: 36.4% contract/format violations, 24.6% tool/recovery failures, 14.6% evidence grounding gaps
- **Category sensitivity**: Highest harness impact on tasks requiring structured data manipulation, tool sequencing, and state tracking

**Relevance to SRF**: Validates the harness-as-composable-unit design. Each of the 13 SRF modes should expose uniform interfaces (Port inputs/outputs) while maintaining execution alignment between LLMNode reasoning and FnNode verifiable artifacts. The StateContract.requires/produces pattern directly addresses the "workspace state" coupling issue identified in Harness-Bench.

**Differentiation opportunity**: SRF's Package abstraction with explicit StateContract and OptKnob tuning provides **formal composability** that existing harnesses lack. Harness-Bench tested harnesses as monolithic systems; SRF makes harnesses first-class evolvable units.

---

### 2. OpenEvolve: Open-Source Evolutionary Coding Agent

**Sources**: 
- [GitHub repository](https://github.com/algorithmicsuperintelligence/openevolve)
- [Blog post](https://algorithmicsuperintelligence.ai/blog/openevolve-overview/)

**What it is**: Open-source implementation of Google DeepMind's AlphaEvolve, using MAP-Elites quality-diversity search with LLM-guided code generation to evolve algorithms.

**Architecture**:
- **Island-based evolution**: Multiple isolated populations with controlled migration (ring topology)
- **Double selection**: Separate programs chosen for performance optimization vs creative inspiration
- **Artifact side-channel**: Execution errors/warnings fed back to LLM for learning
- **Full reproducibility**: Deterministic seeding (default seed=42)

**Benchmark results**:
- GPU kernels: 2.8× speedup on M1 Pro
- Circle packing: Matched state-of-the-art (n=26 problem)
- Function optimization: 100× improvement (random → simulated annealing)
- Prompt engineering: +23% accuracy on HotpotQA

**Strengths**:
- Scientific rigor with exact reproducibility
- Multi-objective optimization via MAP-Elites
- Rich feedback loop (artifacts channel execution context)
- Production-ready (PyPI package, extensive documentation)

**Weaknesses**:
- Cost uncertainty ($0.01-$0.60 per iteration depending on provider)
- Heavy dependency on prompt engineering
- No formal convergence guarantees
- Evaluation overhead (requires custom evaluators per domain)

**Relevance to SRF**: OpenEvolve demonstrates feasibility of evolutionary outer loops for code optimization. SRF's GEPA mode is conceptually similar but with **harness-level evolution** rather than single-function evolution. The MAP-Elites approach could inform SRF's Phase 2 Lab Director for multi-mode orchestration.

**Differentiation opportunity**: SRF operates at **harness/workflow level** (DAG evolution with OptKnobs) rather than function level. OpenEvolve evolves `def solve(...)` implementations; SRF evolves entire research pipelines with multiple agents, eval strategies, and search configurations.

---

### 3. AIDE: AI-Driven Exploration in Code Space

**Source**: [AIDE paper](https://arxiv.org/html/2502.13138v1)

**What it is**: ML engineering agent that frames trial-and-error as tree search in code space, systematically exploring solutions that optimize validation metrics.

**Architecture**:
- **Search Policy (π)**: Hard-coded rule selecting draft/debug/improve actions
- **Coding Operator (f)**: Three specialized prompts for drafting, debugging, improving
- **Summarization Operator (Σ)**: Extracts performance metrics and hints from history tree
- **Tree structure**: Nodes = scripts, edges = improvement attempts

**Performance**:
- **Weco-Kaggle**: 51.38% exceeds average human (vs 0% for AutoGPT)
- **MLE-Bench**: 16.9% medal rate with o1-preview (4× higher than OpenHands)
- **RE-Bench**: Outperformed top AI scientists from DeepMind/Google/Anthropic within 6 hours

**Key innovations**:
- Code-space optimization (not hyperparameter search)
- Stateless optimization vs POMDP framing
- Structured exploration with performance tracking
- Efficient context management via summarization

**Relevance to SRF**: AIDE's tree search methodology is directly applicable to SRF's builder agents. The draft/debug/improve cycle matches the experiment workflow. The summarization approach addresses prompt saturation in long experiments.

**Differentiation opportunity**: AIDE focuses on **single-model single-task** optimization. SRF's multi-mode design allows **strategy comparison across harnesses** for the same research question. AIDE's tree is solution-centric; SRF's tree (in Lab Director phase) would be harness-strategy-centric.

---

### 4. AI Scientist v2: Workshop-Level Automated Discovery

**Sources**:
- [Paper](https://arxiv.org/abs/2504.08066)
- [GitHub repository](https://github.com/sakanaai/ai-scientist-v2)

**What it is**: End-to-end agentic system capable of producing the first peer-review-accepted AI-generated workshop paper. Uses best-first tree search (BFTS) guided by an experiment manager agent.

**Workflow phases**:
1. **Ideation**: LLM brainstorming with Semantic Scholar novelty checks
2. **Experimentation**: Progressive tree search with concurrent node expansion (typical: 3 workers, 21 nodes)
3. **Writing**: Paper generation with citation rounds, VLM feedback on figures

**v1 vs v2**:
- **v1**: Template-based, higher success on well-defined tasks
- **v2**: No templates, generalizes across ML domains, exploratory approach

**Performance**: Achieved peer-review acceptance at ICLR workshop (first AI-generated paper exceeding acceptance threshold)

**Architecture highlights**:
- Built on AIDE project (WecoAI/aideml)
- Automatic debugging of failed experiments (`max_debug_depth`)
- Tree visualization in `unified_tree_viz.html`
- Cost: ~$20-25 per full experiment (ideation + experimentation + writing)

**Relevance to SRF**: AI Scientist v2 represents the **end-to-end pipeline** SRF aims to enable. The tree search manager maps to SRF's Lab Director concept. The template-free v2 approach aligns with SRF's composable Package design.

**Differentiation opportunity**: AI Scientist v2 is **ML-research-specific**. SRF targets **general scientific discovery** (math, optimization, algorithms) with explicit support for multi-harness comparison. AI Scientist v2 has one built-in strategy; SRF offers 13 harness strategies as interchangeable Packages.

---

### 5. FunSearch: Foundation for Evolutionary Code Discovery

**Sources**:
- [GitHub repository](https://github.com/google-deepmind/funsearch)
- [DeepMind blog post](https://deepmind.google/blog/funsearch-making-new-discoveries-in-mathematical-sciences-using-large-language-models/)

**What it is**: Google DeepMind's original evolutionary method for discovering computer programs that solve mathematical and algorithmic problems. Combines LLM generation with automated evaluator and evolutionary search.

**How it works**:
- Iterative loop: select programs from pool → LLM generates variants → evaluate → add best to pool
- Island-based evolutionary process for diversity preservation
- Programs scored automatically, highest-scoring drive next generation

**Achievements**:
- **Cap set problem**: Found cap set of size 512 in dimension 8 (largest improvement in 20 years)
- **Bin packing**: Evolved heuristics outperforming first-fit and best-fit baselines on OR-Library benchmarks

**Evolution to AlphaEvolve**:
- FunSearch: Single function evolution
- AlphaEvolve: Entire codebase evolution, more intricate algorithms

**Relevance to SRF**: FunSearch is the **foundational work** that inspired OpenEvolve and AlphaEvolve. Its island-based diversity preservation is relevant to SRF's multi-mode orchestration. The automated evaluator pattern matches SRF's eval/score.py design.

**Differentiation opportunity**: FunSearch targets **mathematical discovery** (single-function optimization). SRF focuses on **research workflow discovery** (multi-agent DAG optimization). FunSearch proved LLM-driven evolution works for novel discoveries; SRF applies this to harness-level search.

---

### 6. ResearchClawBench: Benchmark for Autonomous Research

**Source**: [ResearchClawBench paper](https://arxiv.org/html/2606.07591)

**What it is**: Benchmark for evaluating autonomous scientific research across 40 tasks from 10 scientific domains (astronomy, chemistry, earth science, energy, information science, life science, materials, mathematics, neuroscience, physics).

**Evaluation methodology**:
- **RADS (Reference-Anchored Discovery Score)**: 100-point scale
  - 50 = target-paper-level re-discovery
  - <50 = insufficient discovery
  - >50 = reference-surpassing evidence
- Expert-curated multimodal rubrics decomposing artifacts into weighted criteria
- Each task grounded in real published paper (hidden during evaluation)

**Current performance baselines**:
- **Best autonomous agent**: Claude Code — 21.5 average
- **Best LLM via ResearchHarness**: Claude-Opus-4.7 — 20.7 average
- **Agent frontier mean**: 24.6 (best per-task across all agents)

**Main failure modes**:
1. Experimental protocol mismatch
2. Evidence mismatch
3. Missing scientific core

**Key finding**: "Current systems remain far from reliable re-discovery" — strongest systems average less than half the score needed for target-paper-level performance.

**Relevance to SRF**: ResearchClawBench is the **evaluation context** for testing SRF's 13 harness implementations. The RADS metric provides objective comparison. The failure mode analysis (protocol/evidence/core mismatches) directly informs what SRF's eval dimensions should measure.

**Differentiation opportunity**: ResearchClawBench evaluates **individual harnesses as black boxes**. SRF makes harness internals **composable and evolvable**. Where ResearchClawBench measures "which harness wins?", SRF enables "which harness configuration wins?" with tunable OptKnobs and DAG structure.

---

### 7. LLM Program Synthesis Benchmarks (2026 Landscape)

**Sources**:
- [LLM Coding Benchmarks Guide](https://www.evidentlyai.com/blog/llm-coding-benchmarks)
- [Openlayer Guide](https://www.openlayer.com/blog/llm-coding-benchmarks-complete-guide)

**Key 2026 benchmarks**:
- **PrismBench**: Dynamic multi-agent framework using MDP to formalize evaluation scenarios
- **CodeARC**: First general-purpose program synthesis benchmark for LLM-powered agents with interactive protocols
- **LiveCodeBench**: Uses problems published after model cutoff (code generation, self-repair, test prediction)
- **EvalPlus**: Extends HumanEval by 80× and MBPP by 35× test cases

**Performance insights**:
- **Synthetic vs real-world gap**: 84-89% correctness on synthetic, only 25-34% on real-world class tasks
- **SWE-bench Verified leaders** (March 2026): MiniMax M2.5 (80.2%), Claude 3.7 Sonnet, GPT-4.5

**Relevance to SRF**: These benchmarks measure **single-task code generation**. SRF's 13 harnesses target **multi-step research workflows** with iteration, hypothesis refinement, and experimental validation. The synthetic vs real-world gap motivates SRF's focus on composable harnesses rather than monolithic solutions.

---

### 8. Harness Engineering Ecosystem

**Sources**:
- [Awesome Harness Engineering](https://github.com/ai-boost/awesome-harness-engineering)
- [Best-of-Agent-Harnesses](https://github.com/RyanAlberts/best-of-Agent-Harnesses)
- [Lilian Weng's Harness Engineering post](https://lilianweng.github.io/posts/2026-07-04-harness/)

**Key insights**:
- **Impact size**: LangChain's coding agent went from 52.8% → 66.5% on TerminalBench by changing only the harness
- **Princeton CORE-Bench**: One model scored 42% under one scaffold, 78% under another
- **Self-Harness concept**: Harnesses that improve themselves via meta-learning

**Harness capabilities** (from NVIDIA blog):
1. Context management
2. Tool orchestration
3. State persistence
4. Permission boundaries
5. Recovery mechanisms
6. Observability/tracing

**Relevance to SRF**: Validates that **harness engineering is a first-class research domain**, not just infrastructure. SRF's 13-harness design treats harnesses as the primary unit of innovation, aligned with the emerging "harness engineering" paradigm.

---

## Prior Knowledge (Archive)

**Status**: No prior archive knowledge found. This is the first research cycle for the SRF project.

**Archive checked**:
- `.factory/archive/memory/context.md` — empty
- `.factory/archive/memory/facts.md` — empty
- No source notes in `.factory/archive/sources/`

---

## Recommended Focus Areas

### 1. **Harness Interface Standardization** (High Impact)

**Insight**: Harness-Bench showed that harness design creates 23.8-point performance variance. SRF's uniform Port interface (`inputs=[Port("task", "task.yaml")]`, `outputs=[Port("best_solution", "best_solution.py")]`) is critical for fair comparison.

**Recommendation**: 
- Define strict StateContract validation in Phase 1 (GEPA mode)
- Ensure all 13 harnesses expose identical Port signatures
- Add eval dimension measuring "execution alignment" (reasoning ↔ artifacts coupling)

**Why it matters**: Without uniform interfaces, SRF becomes a collection of incomparable scripts rather than a composable factory ecosystem.

---

### 2. **Evolutionary Outer Loop Design** (High Impact)

**Insight**: OpenEvolve's MAP-Elites approach maintains diversity while optimizing performance. AIDE's tree search with summarization prevents context saturation. AI Scientist v2's BFTS with concurrent workers achieves exploration-exploitation balance.

**Recommendation**:
- Phase 1: Implement single-mode execution with manual OptKnob tuning
- Phase 2: Port AIDE's tree search for within-mode optimization
- Phase 3: Extend to MAP-Elites grid for cross-mode comparison (Lab Director)

**Why it matters**: The outer loop is SRF's **core differentiator** from existing harnesses. Without it, SRF is just a harness collection; with it, SRF becomes a harness discovery engine.

**Technical approach**:
- Use AIDE's draft/debug/improve pattern for within-mode refinement
- Use MAP-Elites feature dimensions: [harness_type, search_strategy, eval_budget]
- Store experiment results in MemPalace graph for cross-run learning

---

### 3. **Evaluation Sandbox Isolation** (Medium Impact, High Risk)

**Insight**: OpenEvolve warns about cost uncertainty ($0.01-$0.60 per iteration). AI Scientist v2 requires sandboxed environment due to executing LLM-generated code. ResearchClawBench's failure modes include experimental protocol mismatches.

**Recommendation**:
- Build robust eval sandbox in Phase 1 with:
  - Resource limits (CPU/memory/time)
  - Filesystem isolation (chroot or container)
  - Network restrictions (no external API calls)
  - Cost tracking per experiment run
- Add eval dimension for "sandbox safety" (no escapes, no infinite loops)

**Why it matters**: Without sandboxing, a single malformed experiment can crash the entire factory. Cost tracking prevents runaway LLM usage.

---

### 4. **Tracing and Observability** (Medium Impact)

**Insight**: Harness-Bench emphasizes execution alignment — coupling between reasoning, tool actions, and workspace state. Current SRF observability is 0.0% (no logging infrastructure yet).

**Recommendation**:
- Phase 1: Add structured logging to all FnNode callables (using structlog or similar)
- Capture execution traces with spans: [experiment_id, mode_id, node_id, duration, inputs, outputs, errors]
- Store traces in `.factory/traces/` for post-experiment analysis
- Expose trace.jsonl as required output Port for all harnesses

**Why it matters**: Tracing enables debugging failed experiments and provides data for the outer loop to learn from. ResearchClawBench's "evidence mismatch" failures suggest current harnesses lack visibility into their reasoning chains.

---

### 5. **Validation Task Porting Strategy** (High Impact)

**Insight**: SRF Phase 1 targets 3 validation tasks (circle_packing, autocorrelation_inequality, trimul) from the original harness-comparison benchmark. ResearchClawBench baselines show current systems score ~20/100 on real research tasks.

**Recommendation**:
- Start with **circle_packing** (well-defined, OpenEvolve achieved SOTA)
- Use OpenEvolve's result (2.634 sum of radii for n=26) as baseline
- Port task.yaml format from original benchmark, but add:
  - Reference solution for validation
  - Eval rubric with multiple criteria (correctness, efficiency, novelty)
  - Budget limits (LLM calls, execution time, tokens)

**Why it matters**: Validation tasks are the **acceptance test** for Phase 1. If GEPA mode can't match/exceed Flora Jia's GEPA scores on these 3 tasks, the implementation is incorrect.

**Success criterion**: GEPA mode achieves ≥95% of original GEPA scores on the 3 validation tasks with comparable LLM cost.

---

### 6. **Template-Free vs Template-Based Trade-off** (Medium Impact)

**Insight**: AI Scientist v2 shows v1 (template-based) achieves higher success on well-defined tasks, while v2 (template-free) generalizes better but with lower success rates. SRF's GEPA mode will be first — should it use templates?

**Recommendation**:
- **Phase 1 (GEPA)**: Use minimal templates (task schema, eval signature) but allow LLMNode to generate experiment code freely
- **Phase 2 (remaining 12 modes)**: Learn from GEPA failures to decide per-harness template strategy
- Add OptKnob for "template_strictness" [none, schema_only, skeleton, full] to make it tunable

**Why it matters**: Template-free maximizes flexibility but risks higher failure rates. SRF should make this an evolvable knob, not a fixed architectural decision.

---

### 7. **Cross-Harness Knowledge Transfer** (High Impact, Phase 3)

**Insight**: AIDE's summarization operator extracts reusable hints from history. SRF's 13 harnesses will share common patterns (hypothesis generation, eval sandbox, budget tracking).

**Recommendation**:
- Extract common ops to `srf/ops/` shared library:
  - `parse_code(file, lang)` — AST parsing
  - `run_eval(task, solution)` — sandboxed evaluation
  - `track_budget(trace)` — cost accounting
  - `generate_hypothesis(task, mode_config)` — LLM-based ideation
- Phase 3 Lab Director: Learn which ops work best for which task types
- Use MemPalace graph to store cross-harness patterns

**Why it matters**: If each harness reimplements eval sandboxing, the factory has 13× code duplication and 13× debugging surface. Shared ops enable **transfer learning** across harnesses.

---

### 8. **Market Positioning: Harness Discovery vs Harness Execution**

**Insight**: Existing tools fall into two camps:
- **Execution platforms**: OpenClaw, ZeroClaw (harness-bench participants) — run one harness well
- **Single-strategy agents**: AI Scientist v2, AIDE — optimize within one approach

SRF is **neither**: it's a harness discovery platform that compares and evolves strategies.

**Recommendation**:
- Frame SRF as "Meta-research agent" or "Harness optimizer"
- Emphasize the Lab Director (Phase 3) as the key differentiator: "Given research question Q, which of 13 strategies works best? What if we combine them?"
- Target users: AI researchers evaluating harness designs, ML engineers needing multi-strategy search

**Why it matters**: Clear positioning prevents SRF from being perceived as "yet another GEPA implementation." The value is **composability + evolution**, not individual harness performance.

---

## References

### Papers
- [Harness-Bench: Measuring Harness Effects](https://arxiv.org/html/2605.27922v1)
- [AIDE: AI-Driven Exploration in Code Space](https://arxiv.org/html/2502.13138v1)
- [AI Scientist v2: Workshop-Level Discovery](https://arxiv.org/abs/2504.08066)
- [ResearchClawBench: Autonomous Research Benchmark](https://arxiv.org/html/2606.07591)
- [FunSearch: Mathematical Discoveries with LLMs](https://deepmind.google/blog/funsearch-making-new-discoveries-in-mathematical-sciences-using-large-language-models/)

### Code Repositories
- [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve)
- [AI Scientist v2](https://github.com/sakanaai/ai-scientist-v2)
- [FunSearch](https://github.com/google-deepmind/funsearch)

### Benchmark & Landscape Resources
- [LLM Coding Benchmarks Guide](https://www.evidentlyai.com/blog/llm-coding-benchmarks)
- [Awesome Harness Engineering](https://github.com/ai-boost/awesome-harness-engineering)
- [Best-of-Agent-Harnesses](https://github.com/RyanAlberts/best-of-Agent-Harnesses)
- [Harness Engineering for Self-Improvement (Lilian Weng)](https://lilianweng.github.io/posts/2026-07-04-harness/)

---

**Status**: Research complete. 8 focus areas identified, ranked by impact. Phase 1 should prioritize: (1) harness interface standardization, (2) validation task porting, (3) eval sandbox isolation. Phase 2: evolutionary outer loop design. Phase 3: cross-harness knowledge transfer via Lab Director.
