# Researcher Agent Output

- **timestamp:** 2026-08-29T19:00:09Z
- **exit_code:** 0

---

Research complete! I've written a comprehensive tech stack research report to `.factory/strategy/research-techstack.md`.

## Key Findings

**1. Workflow/DAG Execution**: Do NOT adopt Prefect/Dagster/Temporal — remote-factory's Package ecosystem already provides DAG execution, StateContract validation, and OptKnobs. Adding another framework would be redundant.

**2. Sandboxed Code Execution**:
- Phase 1 (MVP): Firejail (~50ms boot, adequate for benchmark tasks)
- Phase 2 (Production): gVisor (~100ms, user-space kernel isolation)
- Phase 3 (If deploying user code): Firecracker microVMs (~125ms, hardware-level isolation)

**3. LLM Integration**: Use httpx (async, HTTP/2) with custom RetryProvider (exponential backoff + rate limit awareness), tiktoken for token pre-counting, Prometheus for cost tracking.

**4. Structured Logging**: structlog + OpenTelemetry is the 2026 Python standard — 80% faster parsing, trace correlation, CNCF-standard OTLP export.

**5. Pydantic State Management**: Pydantic v2 (5-50× faster than v1) for StateContract/OptKnob validation. Guards from factory.md become `@field_validator` or `@model_validator` decorators.

## Recommended Stack

```toml
dependencies = [
    "httpx[http2]>=0.28.0",      # LLM client
    "tiktoken>=0.9.0",            # Token counting
    "structlog>=24.4.0",          # Structured logging
    "pydantic>=2.10.0",           # State validation
    "prometheus-client>=0.21.0",  # Metrics
    "opentelemetry-api>=1.28.0",  # Tracing
    "opentelemetry-sdk>=1.28.0",
]
```

Report includes architecture patterns, framework comparisons, code examples, and 20+ source references.

Sources:
- [Temporal vs Airflow vs Prefect vs Dagster (2026)](https://futurepicker.com/en/temporal-airflow-prefect-dagster-workflow-2026-en/)
- [How to Sandbox AI Agents in 2026](https://dev.to/aiagentengineering/how-to-sandbox-ai-agents-in-2026-firecracker-gvisor-runtimes-isolation-strategies-14pk)
- [LLM API Integration Patterns for Backend Engineers](https://backendbytes.com/articles/llm-api-integration-patterns/)
- [Structlog JSON Logs: OpenTelemetry Python 2026](https://johal.in/structlog-json-logs-middleware-opentelemetry-python-2026/)
- [Execution Flow and State Machine (Pydantic AI)](https://deepwiki.com/pydantic/pydantic-ai/2.2-tools-system)
- [Complete Data Orchestration Comparison 2026](https://www.getorchestra.io/blog/dagster-vs-prefect-vs-airflow-complete-data-orchestration-comparison-2026)
- [Best AI Workflow Orchestration Tools 2026](https://codingprotocols.com/blog/best-ai-workflow-orchestration-tools)
- [Docker Sandboxes in 2026: Secure Code Isolation](https://dev.to/kaixintelligence/docker-sandboxes-in-2026-the-evolution-of-secure-code-isolation-55b8)
- [Agent Sandboxing and Secure Code Execution](https://tianpan.co/blog/2026-03-09-agent-sandboxing-secure-code-execution)
- [Python Code Execution (Firejail)](https://deepwiki.com/TIGER-AI-Lab/verl-tool/4.1-python-code-execution-(firejail))
- [LLM Integration: Rate Limiting & Caching 2026](https://www.groovyweb.co/blog/llm-integration-rate-limiting-caching-fallbacks-2026)
- [Retrying LLM API Calls in Production Python](https://joshuasorrell.com/notes/retrying-llm-api-calls-production-python/)
- [LLM Observability in 2026: Tools & Best Practices](https://tokenmix.ai/blog/llm-observability-2026-tools-best-practices)
- [How to Set Up structlog with OpenTelemetry](https://docs.bswen.com/blog/2026-04-29-structlog-opentelemetry-setup/)
- [Structured Logging in Python with Structlog](https://dev.to/temitopeajao/structured-logging-in-python-with-structlog-correlating-logs-traces-and-errors-in-production-2nlm)
- [How to Send Structured Logs with OpenTelemetry](https://oneuptime.com/blog/post/2026-02-20-opentelemetry-logs-guide/view)
- [Multi-Agent Applications (Pydantic AI)](https://deepwiki.com/pydantic/pydantic-ai/11.2-multi-agent-applications)
- [Pydantic for AI Engineers 2026](https://myengineeringpath.dev/programming/python/pydantic-guide/)
- [How to Validate Data with Pydantic v2 Models](https://oneuptime.com/blog/post/2026-01-21-python-pydantic-v2-validation/view)
---

> **⚠ CEO IDENTITY RE-ANCHOR (Sacred Rule 8)**
> You are the Factory CEO. You orchestrate, delegate, and decide. You do NOT implement.
> If you are about to write code, run tests, do research, or fix bugs — STOP and spawn the appropriate agent.
> Re-read your Permitted/Forbidden Actions lists in the Identity section above.
