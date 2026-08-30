"""Agent execution logic extracted from _factory_shim."""

from __future__ import annotations

from typing import Any

import structlog

from srf.ops.common.code_parsing import extract_code_block


def execute_agent(ctx: Any, agent: Any, log: Any = None) -> str | None:
    """Execute an AgentNode: read inputs, call LLM, write outputs."""
    if log is None:
        log = structlog.get_logger()
    log.info("agent.execute", name=agent.name, model=agent.model, max_turns=agent.max_turns)
    prompt_parts = []
    for f in agent.reads:
        content = ctx.read_text(f)
        if content:
            prompt_parts.append(content)
    user_prompt = "\n\n".join(prompt_parts)

    response = ctx.llm_client.generate(
        system_prompt=agent.system_prompt,
        user_prompt=user_prompt,
        model=agent.model,
        temperature=0.7,
    )

    code = extract_code_block(response.content)
    for f in agent.writes:
        ctx.write_text(f, code)

    from srf.ops.common.budget import record_llm_call
    from srf.ops.common.tracing import log_llm_call

    record_llm_call(ctx, response.input_tokens, response.output_tokens)
    log_llm_call(ctx, agent.name, agent.model, response.input_tokens, response.output_tokens)
    return None
