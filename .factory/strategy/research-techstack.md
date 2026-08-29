# Tech Stack Research — SRF (Scientific Research Factory)

**Generated**: 2026-08-29  
**Target**: SRF scientific research factory - 13 harnesses as composable factory Packages  
**Research Mode**: Targeted tech stack evaluation

---

## Project Summary

SRF (Scientific Research Factory) reimplements 13 AI-driven scientific discovery harnesses (from Flora Jia's harness-comparison benchmark) as composable factory workflow Packages on top of remote-factory's Package ecosystem. A single research question can be refracted through multiple strategies (GEPA, OpenEvolve, AIDE, AI Scientist V2, etc.), each with tunable OptKnobs that the outer loop evolves.

**Current state**: Initial scaffolding phase with eval infrastructure but no implementation yet (0.0% observability, no source files).

**Key architectural requirements**:
- Package-based workflow DAG execution with StateContract validation
- Sandboxed evaluation of LLM-generated code (untrusted)
- Async LLM orchestration with retry, token tracking, budget limits
- Structured tracing for scientific experiment reproducibility
- Pydantic-based state management for workflow validation

---

## Research Findings by Focus Area

### 1. Python Workflow/DAG Execution Frameworks

#### Evaluation: Prefect vs Dagster vs Temporal vs Airflow

**Framework positioning (2026 landscape)**:

| Framework | Core Abstraction | Best For | Learning Curve |
|-----------|-----------------|----------|----------------|
| **Prefect** | @flow/@task decorators on plain Python | Rapid iteration, developer productivity | Gentle (minimal new concepts) |
| **Dagster** | Software-defined assets with lineage | Data warehouses, ML pipelines needing audit trails | Medium (asset-centric thinking) |
| **Temporal** | Durable workflows with event replay | Long-running stateful processes (multi-day) | Steep (determinism constraints) |
| **Airflow** | DAG-based batch scheduling | Legacy systems, mature ecosystem | Steep (DAG parsing, XCom, execution context) |

**Key decision criterion**: "Are your workloads scheduled batch jobs, or long-running stateful processes?" Scientific computing typically falls into the former, making Prefect or Dagster more appropriate than Temporal.

#### Why NOT Use These for SRF

SRF already has **remote-factory's Package ecosystem** as the DAG execution layer. The Packages expose:
- **StateContract**: `requires` and `produces` for file I/O validation
- **FnNode/LLMNode**: Computational graph nodes with `callable_name` imports
- **OptKnobs**: Tunable parameters evolved by outer loop
- **Ports**: Typed inputs/outputs for Package composition

**Verdict**: Do NOT adopt Prefect/Dagster/Temporal. Use remote-factory primitives directly. The research is valuable for understanding trade-offs if future refactoring is needed, but the Package abstraction already provides:
- DAG execution (graph traversal)
- State management (StateContract)
- Retry/fault-tolerance (if needed, add to FnNode wrappers)
- Observability hooks (add to node execution)

**If migrating from Packages were considered** (not recommended):
- **Prefect**: Easiest migration path (minimal framework overhead)
- **Dagster**: Best if asset lineage becomes critical (e.g., "which solution came from which LLM budget?")
- **Temporal**: Overkill unless experiments run multi-day with complex checkpointing needs

---

### 2. Sandboxed Code Execution

#### Security Landscape (2026 Consensus)

**Core finding**: "Shared-kernel container isolation (Docker/runc) isn't adequate for untrusted AI agent code."

#### Five Isolation Levels (weakest → strongest)

| Level | Technology | Isolation Mechanism | Security Verdict | Boot Time | Use Case |
|-------|-----------|---------------------|------------------|-----------|----------|
| 1 | **Docker/Podman** | Namespaces + cgroups | ❌ Insufficient for LLM code | ~1s | Trusted internal code only |
| 2 | **gVisor** | User-space kernel (syscall interception) | ⚠️ Adequate for most AI agents | ~100ms | Google Agent Sandbox, Modal |
| 3 | **Firecracker** | Micro-VMs (dedicated kernel per workload) | ✅ Gold standard | ~125ms | AWS Lambda, E2B, Vercel Sandbox |
| 4 | **Library OS** (LiteBox) | Minimal OS library with controlled primitives | ✅ Strongest, experimental | TBD | Research (February 2026) |
| 5 | **Confidential Computing** | Hardware-encrypted memory (AMD SEV-SNP) | ✅ PII/financial data | N/A | Healthcare, finance |

#### Firejail for Python Code Execution

The PythonCodeTool implementation (TIGER-AI-Lab/verl-tool) provides Firejail isolation:
```bash
firejail \
  --seccomp=socket \         # Block socket creation
  --rlimit-nproc=32 \        # Max 32 processes
  --rlimit-nofile=32 \       # Max 32 open files
  --rlimit-fsize=2m \        # Max 2MB file size
  --rlimit-as=1096m \        # Max ~1GB address space
  python -c "$USER_CODE"
```

**Trade-off**: Firejail uses seccomp-bpf syscall filtering but still shares the host kernel. Adequate for quick sandboxing but weaker than gVisor/Firecracker.

#### Docker Hardening Pattern (if using containers)

```bash
docker run --rm \
  --network none \
  --read-only \
  --cap-drop ALL \
  --cap-add NET_BIND_SERVICE \
  --security-opt no-new-privileges \
  --security-opt seccomp=./hardened.json \
  --memory 256m \
  --cpus 0.5 \
  python:3.12-alpine python eval.py
```

**Critical warnings**:
- Mounting `/var/run/docker.sock` grants host root access — never do this
- Path traversal attacks bypass simple prefix checks via symlinks (multiple 2025 CVEs)

#### Recommended Stack for SRF

**Phase 1 (MVP)**: **Subprocess + Firejail**
- Fastest to implement for `srf/ops/eval_sandbox.py`
- Adequate security for controlled benchmark tasks (circle_packing, trimul, etc.)
- Python: `subprocess.run(['firejail', '--profile=srf.profile', 'python', solution_path])`

**Phase 2 (Production)**: **gVisor via runsc**
- Stronger isolation without microVM overhead
- Google Agent Sandbox integration if on Kubernetes
- Python: Switch subprocess executor to `runsc run` with OCI runtime spec

**Phase 3 (If deploying untrusted user code)**: **Firecracker microVMs**
- Use E2B SDK (managed) or microsandbox (self-hosted libkrun)
- Sub-200ms startup with hardware-level isolation
- Data gravity consideration: If experiments move GBs of data, prefer self-hosted to avoid API egress costs

#### Subprocess Isolation Pattern (Python)

**Import filtering** (enforce before user code runs):
```python
import sys
import builtins

_safe_builtins = {
    'abs', 'all', 'any', 'enumerate', 'filter', 'len', 'list',
    'map', 'max', 'min', 'range', 'sorted', 'sum', 'tuple', 'zip'
}

def lock_imports():
    """Disable dangerous imports."""
    sys.modules['os'] = None
    sys.modules['subprocess'] = None
    sys.modules['socket'] = None
    sys.modules['ctypes'] = None
    
    # Restrict builtins
    safe = {k: v for k, v in builtins.__dict__.items() if k in _safe_builtins}
    builtins.__dict__.clear()
    builtins.__dict__.update(safe)

# Execute user code
lock_imports()
exec(untrusted_code, {"__builtins__": builtins})
```

**Warning**: This is a defense-in-depth layer, NOT a primary sandbox. Combine with Firejail/gVisor.

---

### 3. LLM Integration Patterns

#### Core Architecture: Provider Abstraction Layer

**2026 industry pattern**: Single provider interface handling both `complete()` and `stream()` methods. This becomes the "seam where you compose retry, fallback, observability, and cost tracking without touching business logic."

```python
from abc import ABC, abstractmethod
from typing import Protocol, Iterator
from dataclasses import dataclass

class Provider(Protocol):
    def complete(self, ctx: Context, req: CompletionRequest) -> CompletionResponse: ...
    def stream(self, ctx: Context, req: CompletionRequest) -> Iterator[StreamChunk]: ...

@dataclass
class CompletionRequest:
    model: str
    messages: list[Message]
    tools: list[ToolDefinition] = None
    max_tokens: int = None
    temperature: float = None
```

#### Retry Strategy: Exponential Backoff with Rate Limit Respect

**Decision tree**:
- **429 (Rate Limit)**: Read `Retry-After` header → sleep exact duration (no jitter)
- **500-504 (Server Errors)**: Exponential backoff with full jitter
- **400 (Invalid Request)**: Never retry (same prompt will fail again)
- **401/403 (Auth)**: Never retry (requires human intervention)

**Exponential backoff formula**:
```python
import random

def calculate_backoff(attempt: int, initial: float = 1.0, max_backoff: float = 60.0) -> float:
    """Full jitter: wait between 0 and exponential ceiling."""
    base = initial * (2 ** (attempt - 1))
    base = min(base, max_backoff)
    return random.random() * base  # [0, base)
```

**Why full jitter?** Prevents "thundering herd" when many requests fail simultaneously and retry at the same interval.

#### Token Budget Enforcement: Pre-Flight Validation

**Critical pattern**: "Count tokens before making the API call. Catch context-window overflows client-side before paying for 400 errors."

```python
import tiktoken

class TokenCounter:
    PER_MESSAGE_OVERHEAD = 4  # <im_start>{role}\ncontent<im_end>\n
    REPLY_PRIMING = 2
    
    def count_messages(self, model: str, messages: list[Message]) -> int:
        enc = tiktoken.encoding_for_model(model)
        total = self.REPLY_PRIMING
        for msg in messages:
            tokens = enc.encode(msg.content)
            total += len(tokens) + self.PER_MESSAGE_OVERHEAD
        return total
```

**Sliding window context management**:
```python
def sliding_window(messages: list[Message], max_tokens: int, model: str) -> list[Message]:
    """Keep system prompt + recent context within token budget."""
    system = [m for m in messages if m.role == "system"]
    conversation = [m for m in messages if m.role != "system"]
    
    result = system.copy()
    budget = max_tokens - count_messages(model, system)
    
    # Walk newest-to-oldest, keep what fits
    kept = []
    for msg in reversed(conversation):
        msg_tokens = count_messages(model, [msg])
        if msg_tokens > budget:
            break
        kept.insert(0, msg)
        budget -= msg_tokens
    
    return result + kept
```

#### Async Execution & Streaming

**Backpressure control** (prevents OOM with slow clients):
```python
import asyncio

async def stream_with_backpressure(request, provider: Provider):
    """FastAPI/Starlette streaming endpoint with bounded buffer."""
    async def event_generator():
        queue = asyncio.Queue(maxsize=16)  # bounded buffer prevents unbounded growth
        
        async def producer():
            try:
                async for chunk in provider.stream(request.context, request.body):
                    await queue.put(chunk)  # blocks if queue full
            finally:
                await queue.put(None)  # sentinel
        
        producer_task = asyncio.create_task(producer())
        
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {json.dumps(chunk.dict())}\n\n"
        finally:
            producer_task.cancel()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"}  # disable nginx buffering
    )
```

#### Cost Circuit Breaker: Monthly Budget Enforcement

**OWASP LLM10 risk**: "Without cost tracking, a runaway loop will surprise you with a $2,000 bill before you notice."

```python
from prometheus_client import Counter

token_usage = Counter('llm_tokens_total', 'Token usage', ['model', 'type'])
request_cost = Counter('llm_cost_dollars_total', 'API cost', ['model'])

PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},  # per 1M tokens
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

class CostTracker:
    def record(self, model: str, usage: TokenUsage):
        price = PRICING[model]
        cost = (usage.prompt_tokens / 1_000_000) * price["input"] + \
               (usage.completion_tokens / 1_000_000) * price["output"]
        
        token_usage.labels(model=model, type="prompt").inc(usage.prompt_tokens)
        token_usage.labels(model=model, type="completion").inc(usage.completion_tokens)
        request_cost.labels(model=model).inc(cost)
        
        # Check monthly budget
        if self.current_spend >= self.monthly_budget:
            logger.error("LLM budget exhausted", extra={"spend": self.current_spend})
            self.kill_switch()  # alert on-call, throttle requests, etc.
```

#### Production Checklist (10 Must-Haves)

1. **Provider abstraction**: All calls through single interface
2. **HTTP/2 multiplexing**: `httpx.AsyncClient(http2=True)` in Python
3. **Retry logic**: Exponential backoff, max 3 attempts, respect `Retry-After`
4. **Fallback chain**: Primary → Claude → cheaper model
5. **Token pre-counting**: Validate before API call
6. **Cost tracking**: Prometheus metrics + 90% budget alert
7. **Streaming**: SSE with `X-Accel-Buffering: no` header
8. **Tool validation**: Schema validation before execution (30s timeout)
9. **Observability**: OpenTelemetry spans, structured logging
10. **Prompt versioning**: Templates as files, not hardcoded strings

#### Recommended Stack for SRF

**Base library**: `httpx` with HTTP/2 (not `requests`)
- Async-first: `httpx.AsyncClient()` for concurrent LLM calls
- Connection pooling for multi-turn conversations

**Retry layer**: Custom `RetryProvider` wrapping base client
- Max 3 retries with full-jitter exponential backoff
- Rate limit awareness (`Retry-After` header)

**Cost tracking**: Prometheus metrics + alerting
- Track tokens per model/harness/task dimension
- Budget circuit breaker at 90% monthly spend

**Token counting**: `tiktoken` for pre-flight validation
- Critical for avoiding 400 errors on context overflow
- Enables sliding-window context management

**Streaming**: FastAPI with bounded asyncio.Queue
- 16-element queue prevents OOM with slow consumers
- Per-write 10s deadline to detect disconnected clients

---

### 4. Structured Tracing/Logging for Scientific Experiments

#### Core Stack: structlog + OpenTelemetry

**Industry consensus (2026)**: structlog for structured log formatting + OpenTelemetry for distributed tracing is the Python standard. "By 2026, OpenTelemetry has become the second-most active CNCF project, just behind Kubernetes."

**Performance**: structlog JSON reduces parsing time by 80% vs plain logs. Overhead: ~7.4% vs 30% with manual stdlib extraction.

#### Integration Pattern

```python
from opentelemetry import trace
import structlog

def add_open_telemetry_spans(_, __, event_dict):
    """Adds OpenTelemetry trace context to structlog events."""
    span = trace.get_current_span()
    if not span.is_recording():
        event_dict["span"] = None
        return event_dict
    
    ctx = span.get_span_context()
    event_dict["span"] = {
        "span_id": format(ctx.span_id, "016x"),
        "trace_id": format(ctx.trace_id, "032x"),
    }
    return event_dict

# CRITICAL: OTel MUST be initialized BEFORE structlog
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Then configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_open_telemetry_spans,  # Custom processor injects trace_id/span_id
        structlog.processors.JSONRenderer(),
    ],
)
```

#### Output Format

```json
{
  "event": "gepa_iteration_complete",
  "iteration": 5,
  "best_score": 0.87,
  "llm_tokens": 4521,
  "span": {
    "trace_id": "abc123def45678901234567890123456",
    "span_id": "0011223344556677"
  },
  "timestamp": "2026-08-29T14:32:01.123456Z",
  "level": "info"
}
```

**Key benefit**: Search logs by `trace_id` → jump directly to distributed trace showing full experiment DAG execution.

#### Scientific Experiment Requirements

For SRF, structured logging must capture:
1. **Experiment metadata**: harness name, task, OptKnob settings, random seed
2. **LLM interactions**: model, prompt hash, tokens, cost, latency
3. **Eval results**: score, pass/fail, error messages
4. **Resource usage**: CPU time, memory peak, sandbox executions
5. **Trace lineage**: Which solution came from which LLM call?

**Structlog context binding**:
```python
log = structlog.get_logger()

# Bind experiment context once
log = log.bind(
    harness="gepa",
    task="circle_packing",
    run_id=run_id,
    knobs={"max_iters": 10, "temperature": 0.7}
)

# All subsequent logs include context
log.info("iteration_start", iteration=i)
log.info("llm_call", model="sonnet", tokens=1234, cost=0.003)
log.info("eval_complete", score=0.85)
```

#### Production Setup with OTLP Export

```python
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Export to OpenTelemetry Collector → Jaeger/Tempo/Honeycomb
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317"))
)
```

#### Common Pitfalls

1. **Wrong initialization order**: Configuring structlog before OTel → no spans found
2. **Incorrect ID formatting**: Use `format(ctx.trace_id, "032x")` for 32-char hex (not decimal)
3. **Non-recording spans**: Always check `span.is_recording()` to handle sampling/mocks
4. **Missing correlation**: Not binding experiment ID early → can't group logs by run

#### Recommended Stack for SRF

**Phase 1**: structlog with JSON renderer
- Immediate structured logging (0.0% → 100% observability)
- File output: `srf/logs/{harness}_{task}_{run_id}.jsonl`
- One log line per iteration/eval/LLM call

**Phase 2**: Add OpenTelemetry spans
- Instrument Package execution (one span per FnNode/LLMNode)
- Export to Jaeger/Tempo for visualization
- Correlation: `trace_id` links logs → spans → full DAG execution

**Phase 3**: Metrics with Prometheus
- LLM token usage by harness/task
- Eval scores over time
- Resource usage (CPU/memory/sandbox time)

---

### 5. Pydantic State Management

#### Pydantic AI: Graph-Based Execution Model

Pydantic AI (released 2026) provides a **state machine architecture** for multi-agent workflows, powered by the `pydantic-graph` library. This is directly relevant to SRF's Package orchestration.

**Core abstraction**: AgentRun executes as a state machine cycling through node types:
1. **UserPromptNode**: Assembles prompts, handles deferred tool results
2. **ModelRequestNode**: Sends LLM requests, tracks usage, updates message history
3. **CallToolsNode**: Processes responses, executes tools, validates outputs, determines continuation

#### State Container: GraphAgentState

```python
from pydantic import BaseModel
from typing import List

class GraphAgentState(BaseModel):
    message_history: List[Message]
    usage: TokenUsage  # tracks tokens, request counts, tool call counts
    output_retries_used: int = 0
    run_step: int = 0
    run_id: str  # UUID7
    conversation_id: str
    pending_messages: List[Message] = []
    
    def consume_output_retry(self) -> None:
        """Increment retry counter, raise if limit exceeded."""
        self.output_retries_used += 1
        if self.output_retries_used > self.max_retries:
            raise UnexpectedModelBehavior("Validation retry limit exceeded")
```

**Retry mechanism**: On validation failure, generates `RetryPromptPart` with error details, loops back to UserPromptNode. Max retries configurable (default: 1).

#### Workflow Validation Patterns

**Field Validators** (individual field validation):
```python
from pydantic import BaseModel, field_validator

class OptKnob(BaseModel):
    name: str
    bounds: list[float]
    default: float
    
    @field_validator('default')
    @classmethod
    def default_in_bounds(cls, v: float, info) -> float:
        bounds = info.data.get('bounds')
        if bounds and not (bounds[0] <= v <= bounds[1]):
            raise ValueError(f"default {v} not in bounds {bounds}")
        return v
```

**Model Validators** (cross-field validation):
```python
from pydantic import model_validator

class StateContract(BaseModel):
    requires: list[str]  # input file paths
    produces: list[str]  # output file paths
    
    @model_validator(mode='after')
    def no_overlap(self) -> 'StateContract':
        overlap = set(self.requires) & set(self.produces)
        if overlap:
            raise ValueError(f"Files appear in both requires and produces: {overlap}")
        return self
```

**Wrap mode** (for advanced workflows):
```python
@model_validator(mode='wrap')
@classmethod
def inject_defaults(cls, v, handler, info):
    """Inject defaults before main validation."""
    if isinstance(v, dict):
        v.setdefault('timeout', 30)
    return handler(v)  # Continue to field validators
```

#### Multi-Agent Orchestration Patterns

Pydantic AI supports several patterns (simplest → most complex):

1. **Delegation**: Single agent calls sub-agents via tool functions
2. **Sequential**: Agent A → Agent B → Agent C pipeline
3. **Parallel**: Multiple agents run concurrently, results merged
4. **Graph-based**: Complex DAG with conditional branching (LangGraph-style)

**Example: Sequential pattern**:
```python
async def research_and_build(task: str):
    # Agent 1: Research
    research_result = await researcher_agent.run(task)
    
    # Agent 2: Build (using research)
    build_result = await builder_agent.run(
        f"Implement: {task}\nResearch: {research_result.data}"
    )
    
    return build_result
```

#### Pydantic v2 Performance

"Pydantic v2 is 5 to 50 times faster than v1 thanks to its Rust-based validation core."

**Partial validation** (for streaming LLM outputs):
```python
from pydantic import ValidationError

class Solution(BaseModel):
    code: str
    explanation: str
    score: float | None = None

# During streaming
try:
    partial = Solution.model_validate(incomplete_data, strict=False)
except ValidationError:
    pass  # Still streaming, validation will pass later

# After streaming completes
final = Solution.model_validate(complete_data, strict=True)
```

#### Recommended Patterns for SRF

**StateContract validation** (already planned in factory.md):
```python
class StateContract(BaseModel):
    requires: list[str]  # ["task.yaml"]
    produces: list[str]  # ["best_solution.py", "trace.jsonl"]
    
    @model_validator(mode='after')
    def validate_file_existence_on_run(self) -> 'StateContract':
        """Check required files exist before Package execution."""
        # Validation logic here
        return self
```

**OptKnob bounds validation**:
```python
class OptKnob(BaseModel):
    name: str
    bounds: list[float]
    default: float
    current: float
    
    @field_validator('bounds')
    @classmethod
    def non_empty_bounds(cls, v: list[float]) -> list[float]:
        if not v:
            raise ValueError("OptKnob bounds must be non-empty list")
        return v
    
    @field_validator('current')
    @classmethod
    def current_in_bounds(cls, v: float, info) -> float:
        bounds = info.data.get('bounds', [])
        if bounds and not (bounds[0] <= v <= bounds[1]):
            raise ValueError(f"current {v} not in bounds {bounds}")
        return v
```

**Package validation** (uniform interface guard):
```python
class Package(BaseModel):
    name: str
    inputs: list[Port]
    outputs: list[Port]
    nodes: list[FnNode | LLMNode]
    
    @model_validator(mode='after')
    def validate_uniform_interface(self) -> 'Package':
        """Enforce: all mode Packages expose uniform interface."""
        required_inputs = {"task"}  # Port("task", "task.yaml")
        required_outputs = {"best_solution", "trace"}
        
        input_names = {p.name for p in self.inputs}
        output_names = {p.name for p in self.outputs}
        
        if not required_inputs.issubset(input_names):
            raise ValueError(f"Missing required inputs: {required_inputs - input_names}")
        if not required_outputs.issubset(output_names):
            raise ValueError(f"Missing required outputs: {required_outputs - output_names}")
        
        return self
```

---

## Recommended Tech Stack

### Core Stack (Minimal Production Dependencies)

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Package execution** | remote-factory primitives | Already provides DAG, StateContract, OptKnobs — do NOT add Prefect/Dagster |
| **Sandboxed eval** | Firejail → gVisor (Phase 2) | Firejail adequate for MVP, gVisor for production untrusted code |
| **LLM client** | httpx (async, HTTP/2) | Industry standard for async API calls with connection pooling |
| **Retry logic** | Custom RetryProvider | Full jitter exponential backoff with rate-limit awareness |
| **Token counting** | tiktoken | Pre-flight validation to avoid context overflow |
| **Structured logging** | structlog + OpenTelemetry | 80% faster parsing, trace correlation, CNCF standard |
| **State validation** | Pydantic v2 | 5-50× faster than v1, Rust-based validation core |
| **Metrics** | Prometheus client | Token usage, cost tracking, eval scores |
| **Tracing export** | OTLP → Jaeger/Tempo | Distributed trace visualization |

### Implementation Phases

#### Phase 1: Scaffolding + GEPA (Current Focus)

**Must-have**:
1. **Eval sandbox**: `srf/ops/eval_sandbox.py` using subprocess + Firejail
2. **LLM client**: `srf/ops/llm_client.py` with httpx async + retry logic
3. **Structured logging**: structlog with JSON renderer, one log file per experiment
4. **State validation**: Pydantic models for StateContract, OptKnob, Package

**Dependencies** (add to pyproject.toml):
```toml
[project]
dependencies = [
    "httpx[http2]>=0.28.0",
    "tiktoken>=0.9.0",
    "structlog>=24.4.0",
    "pydantic>=2.10.0",
    "prometheus-client>=0.21.0",
    "opentelemetry-api>=1.28.0",
    "opentelemetry-sdk>=1.28.0",
]
```

**File structure**:
```
srf/
├── ops/
│   ├── eval_sandbox.py      # Firejail wrapper for untrusted code
│   ├── llm_client.py         # httpx async client with retry
│   ├── token_counter.py      # tiktoken pre-flight validation
│   └── cost_tracker.py       # Prometheus metrics
├── logging/
│   └── config.py             # structlog + OTel setup
└── models/
    ├── state_contract.py     # Pydantic StateContract
    ├── opt_knob.py           # Pydantic OptKnob
    └── package.py            # Pydantic Package validation
```

#### Phase 2: Production Hardening

**Upgrades**:
1. **Sandbox**: Migrate eval_sandbox.py from Firejail → gVisor (runsc)
2. **Tracing**: Add OpenTelemetry OTLP export to Jaeger/Tempo
3. **Cost limits**: Budget circuit breaker with alerting at 90% threshold
4. **Streaming**: Add streaming support for long-running LLM calls

#### Phase 3: Advanced Features

**If needed**:
1. **Micro-VMs**: Firecracker via E2B SDK for untrusted user-submitted tasks
2. **Workflow DAG visualization**: Export Package graph to Mermaid/GraphViz
3. **A/B testing**: Fallback chain (GPT-4o → Claude → cheaper model)

---

## Architecture Patterns

### 1. Layered Provider Pattern (LLM Integration)

```
Business Logic (srf/modes/gepa.py)
       ↓
Provider Interface (abstract complete/stream)
       ↓
┌──────┴──────┐
│  Retry Layer │ (exponential backoff, rate limit awareness)
└──────┬──────┘
       ↓
┌──────┴──────┐
│  Cost Tracker│ (Prometheus metrics, budget enforcement)
└──────┬──────┘
       ↓
┌──────┴──────┐
│ HTTP Client  │ (httpx async with HTTP/2)
└─────────────┘
```

**Key principle**: Each layer is independently useful and composable. Retry logic doesn't know about cost tracking; cost tracking doesn't know about HTTP details.

### 2. Sandbox Execution Pattern

```
srf/ops/eval_sandbox.py
  ├─→ lock_imports()          # Disable os, subprocess, socket, ctypes
  ├─→ write_temp_file()       # Isolated /tmp/srf-eval-{uuid}/
  ├─→ subprocess.run([
  │     'firejail',
  │     '--profile=srf.profile',
  │     '--rlimit-as=1096m',
  │     'python', temp_file
  │   ])
  └─→ parse_output()          # JSON from stdout, timeout 30s
```

**Defense in depth**: Import filtering + resource limits + syscall filtering + read-only filesystem.

### 3. Structured Logging with Trace Correlation

```
Package.execute()
  ├─→ with tracer.start_as_current_span(f"package.{self.name}"):
  │     log = log.bind(package=self.name, run_id=run_id)
  │     
  │     for node in self.nodes:
  │       with tracer.start_as_current_span(f"node.{node.name}"):
  │         log.info("node_start", node=node.name)
  │         result = node.execute()
  │         log.info("node_complete", node=node.name, result=result)
```

**Output**:
```json
{"event": "node_start", "node": "parse_task", "package": "gepa", "run_id": "abc123", "span": {"trace_id": "...", "span_id": "..."}}
{"event": "node_complete", "node": "parse_task", "package": "gepa", "run_id": "abc123", "span": {...}}
```

Search logs by `run_id` → get full experiment. Search by `trace_id` → see distributed trace DAG.

### 4. Pydantic Validation Pipeline

```
factory.begin()
  ├─→ Package.model_validate(yaml_data)
  │     ├─→ Field validators (OptKnob bounds, StateContract overlap)
  │     ├─→ Model validators (uniform interface, callable_name imports)
  │     └─→ Raise ValidationError if guards violated
  │
  └─→ Package.execute()
        ├─→ StateContract.validate_requires() # Files exist before run
        └─→ StateContract.validate_produces() # Files created after run
```

**Guards as Pydantic validators**: All guards from factory.md become `@field_validator` or `@model_validator` decorators.

---

## Framework Comparisons

### Workflow Orchestration: Prefect vs Dagster vs Temporal

| Criterion | Prefect | Dagster | Temporal | remote-factory (current) |
|-----------|---------|---------|----------|-------------------------|
| **Learning curve** | Gentle | Medium | Steep | None (already integrated) |
| **Python-native** | ✅ @flow/@task | ✅ @asset | ⚠️ Multi-language | ✅ FnNode/LLMNode |
| **State management** | Task state in DB | Asset lineage + state | Event replay | StateContract |
| **Retry/fault-tolerance** | Built-in | Built-in | Core feature | Add to FnNode wrappers |
| **Data lineage** | ❌ Weak | ✅ First-class | ❌ Not data-focused | ⚠️ Manual (trace.jsonl) |
| **Operational complexity** | Medium | Medium | High | Low (no server) |
| **Best for** | Rapid iteration | Data warehouse | Long-running processes | Embedded workflows |
| **SRF fit** | ⚠️ Redundant | ⚠️ Redundant | ❌ Overkill | ✅ **Use this** |

**Verdict**: Continue using remote-factory Packages. Do NOT add Prefect/Dagster/Temporal.

### Sandboxing: Docker vs Firejail vs gVisor vs Firecracker

| Isolation | Boot Time | Security | Compatibility | Cost | SRF Recommendation |
|-----------|-----------|----------|---------------|------|-------------------|
| **Docker** | ~1s | ❌ Shared kernel | ✅ 100% | Low | ❌ Inadequate for LLM code |
| **Firejail** | ~50ms | ⚠️ Seccomp filtering | ✅ High | Low | ✅ Phase 1 MVP |
| **gVisor** | ~100ms | ✅ User-space kernel | ⚠️ 95% syscall coverage | Medium | ✅ Phase 2 production |
| **Firecracker** | ~125ms | ✅ Dedicated kernel | ✅ Full VM isolation | High | ⚠️ Phase 3 if deploying user code |

**Verdict**: Start with Firejail, migrate to gVisor for production. Only use Firecracker if deploying SRF as a service for untrusted users.

### LLM Libraries: httpx vs requests vs anthropic SDK

| Library | HTTP/2 | Async | Connection Pooling | Retry Logic | SRF Recommendation |
|---------|--------|-------|-------------------|-------------|-------------------|
| **httpx** | ✅ | ✅ | ✅ | ❌ (add custom) | ✅ **Use this** |
| **requests** | ❌ | ❌ | ⚠️ Session only | ❌ | ❌ Sync-only, no HTTP/2 |
| **anthropic SDK** | ✅ | ✅ | ✅ | ✅ Built-in | ⚠️ Vendor lock-in |
| **openai SDK** | ✅ | ✅ | ✅ | ✅ Built-in | ⚠️ Vendor lock-in |

**Verdict**: Use httpx with custom `RetryProvider` wrapper. Vendor SDKs are convenient but prevent fallback chains (GPT-4o → Claude → cheaper model).

### Logging: structlog vs standard logging vs loguru

| Library | Structured | OpenTelemetry | Performance | JSON Output | SRF Recommendation |
|---------|-----------|---------------|-------------|-------------|-------------------|
| **structlog** | ✅ | ✅ (via processor) | Fast (7% overhead) | ✅ | ✅ **Use this** |
| **logging** | ❌ (via adapter) | ⚠️ Manual | Baseline | ⚠️ Manual | ❌ No native structure |
| **loguru** | ✅ | ❌ No direct support | Fast | ✅ | ⚠️ Less OTel integration |

**Verdict**: structlog + OpenTelemetry is the 2026 Python standard. 80% faster parsing, native trace correlation.

---

## References

### Workflow Orchestration
- [Temporal vs Airflow vs Prefect vs Dagster (2026)](https://futurepicker.com/en/temporal-airflow-prefect-dagster-workflow-2026-en/)
- [Complete Data Orchestration Comparison 2026](https://www.getorchestra.io/blog/dagster-vs-prefect-vs-airflow-complete-data-orchestration-comparison-2026)
- [Best AI Workflow Orchestration Tools 2026](https://codingprotocols.com/blog/best-ai-workflow-orchestration-tools)

### Sandboxed Execution
- [How to Sandbox AI Agents in 2026](https://dev.to/aiagentengineering/how-to-sandbox-ai-agents-in-2026-firecracker-gvisor-runtimes-isolation-strategies-14pk)
- [Docker Sandboxes in 2026: Secure Code Isolation](https://dev.to/kaixintelligence/docker-sandboxes-in-2026-the-evolution-of-secure-code-isolation-55b8)
- [Agent Sandboxing and Secure Code Execution](https://tianpan.co/blog/2026-03-09-agent-sandboxing-secure-code-execution)
- [Python Code Execution (Firejail)](https://deepwiki.com/TIGER-AI-Lab/verl-tool/4.1-python-code-execution-(firejail))

### LLM Integration Patterns
- [LLM API Integration Patterns for Backend Engineers](https://backendbytes.com/articles/llm-api-integration-patterns/)
- [LLM Integration: Rate Limiting & Caching 2026](https://www.groovyweb.co/blog/llm-integration-rate-limiting-caching-fallbacks-2026)
- [Retrying LLM API Calls in Production Python](https://joshuasorrell.com/notes/retrying-llm-api-calls-production-python/)
- [LLM Observability in 2026: Tools & Best Practices](https://tokenmix.ai/blog/llm-observability-2026-tools-best-practices)

### Structured Logging & Tracing
- [Structlog JSON Logs: OpenTelemetry Python 2026](https://johal.in/structlog-json-logs-middleware-opentelemetry-python-2026/)
- [How to Set Up structlog with OpenTelemetry](https://docs.bswen.com/blog/2026-04-29-structlog-opentelemetry-setup/)
- [Structured Logging in Python with Structlog](https://dev.to/temitopeajao/structured-logging-in-python-with-structlog-correlating-logs-traces-and-errors-in-production-2nlm)
- [How to Send Structured Logs with OpenTelemetry](https://oneuptime.com/blog/post/2026-02-20-opentelemetry-logs-guide/view)

### Pydantic State Management
- [Execution Flow and State Machine (Pydantic AI)](https://deepwiki.com/pydantic/pydantic-ai/2.2-tools-system)
- [Multi-Agent Applications (Pydantic AI)](https://deepwiki.com/pydantic/pydantic-ai/11.2-multi-agent-applications)
- [Pydantic for AI Engineers 2026](https://myengineeringpath.dev/programming/python/pydantic-guide/)
- [How to Validate Data with Pydantic v2 Models](https://oneuptime.com/blog/post/2026-01-21-python-pydantic-v2-validation/view)

---

**End of Report**
