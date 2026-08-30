"""Local shim providing factory workflow primitives.

Provides Package, Sequential, Parallel, Conditional, Loop, FnNode, LLMNode,
GateNode, OptKnob, Port, MemoryDeclaration, StateContract, Edge, Workflow,
and WorkflowExecutor — all with functional execution semantics.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import structlog

from srf.ops.common.code_parsing import extract_code_block

logger = structlog.get_logger()


@dataclass
class Port:
    name: str
    file_pattern: str


@dataclass
class StateContract:
    requires: set[str] = field(default_factory=set)
    produces: set[str] = field(default_factory=set)


@dataclass
class OptKnob:
    name: str
    kind: str
    default: Any
    bounds: list[Any]
    node_id: str
    description: str = ""


@dataclass
class MemoryDeclaration:
    namespace: str
    kind: str
    retention: str


@dataclass
class Edge:
    source: str
    target: str


@dataclass
class FnNode:
    name: str
    callable_name: str
    reads: set[str] = field(default_factory=set)
    writes: set[str] = field(default_factory=set)


@dataclass
class LLMNode:
    name: str
    model: str
    temperature: float
    system_prompt: str
    reads: set[str] = field(default_factory=set)
    writes: set[str] = field(default_factory=set)


@dataclass
class GateNode:
    name: str
    evaluator_command: str


@dataclass
class Package:
    name: str
    nodes: list[Any] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    inputs: list[Port] = field(default_factory=list)
    outputs: list[Port] = field(default_factory=list)
    state_contract: StateContract | None = None
    knobs: list[OptKnob] = field(default_factory=list)
    memory: list[MemoryDeclaration] = field(default_factory=list)


@dataclass
class Sequential:
    name: str
    children: list[Any] = field(default_factory=list)


@dataclass
class Parallel:
    name: str
    children: list[Any] = field(default_factory=list)


@dataclass
class Conditional:
    name: str
    gate: GateNode | None = None
    branches: dict[str, Any] = field(default_factory=dict)


@dataclass
class Loop:
    name: str
    body: Any = None
    gate: GateNode | None = None
    max_iterations: int = 500


@dataclass
class AgentNode:
    name: str
    model: str
    system_prompt: str
    max_turns: int = 10
    reads: set[str] = field(default_factory=set)
    writes: set[str] = field(default_factory=set)


@dataclass
class Workflow:
    name: str
    root: Any = None
    knobs: list[OptKnob] = field(default_factory=list)
    memory: list[MemoryDeclaration] = field(default_factory=list)


class LLMResponse:
    __slots__ = ("content", "input_tokens", "output_tokens")

    def __init__(self, content: str, input_tokens: int = 0, output_tokens: int = 0):
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class LLMClient(Protocol):
    def generate(
        self, system_prompt: str, user_prompt: str, model: str, temperature: float
    ) -> LLMResponse: ...


class HttpxLLMClient:
    MODEL_MAP = {
        "sonnet": "claude-sonnet-4-20250514",
        "opus": "claude-opus-4-20250514",
        "haiku": "claude-haiku-4-5-20251001",
    }

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required for LLM calls")

    def generate(
        self, system_prompt: str, user_prompt: str, model: str, temperature: float
    ) -> LLMResponse:
        import httpx

        model_id = self.MODEL_MAP.get(model, model)
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model_id,
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": temperature,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["content"][0]["text"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )


class OpenAILLMClient:
    MODEL_MAP = {
        "sonnet": "gpt-4o-mini",
        "opus": "gpt-4o",
        "haiku": "gpt-4o-mini",
    }

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI LLM calls")

    def generate(
        self, system_prompt: str, user_prompt: str, model: str, temperature: float
    ) -> LLMResponse:
        import httpx

        model_id = self.MODEL_MAP.get(model, model)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 8192,
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            content=content,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
        )


class VertexAILLMClient:
    MODEL_MAP = {
        "sonnet": "claude-sonnet-4-6",
        "opus": "claude-opus-4-6",
        "haiku": "claude-haiku-4-5",
    }

    def __init__(
        self,
        project_id: str | None = None,
        region: str | None = None,
    ):
        from anthropic import AnthropicVertex

        self.project_id = project_id or os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID", "")
        self.region = region or os.environ.get("CLOUD_ML_REGION", "us-east5")
        if self.region == "global":
            self.region = "us-east5"
        self.client = AnthropicVertex(project_id=self.project_id, region=self.region)

    def generate(
        self, system_prompt: str, user_prompt: str, model: str, temperature: float
    ) -> LLMResponse:
        model_id = self.MODEL_MAP.get(model, model)
        msg = self.client.messages.create(
            model=model_id,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            extra_body={"temperature": temperature},
        )
        content = msg.content[0].text
        return LLMResponse(
            content=content,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
        )


class MockLLMClient:
    def __init__(self, responses: list[str] | None = None):
        self._responses = list(responses or [])
        self._index = 0

    def generate(
        self, system_prompt: str, user_prompt: str, model: str, temperature: float
    ) -> LLMResponse:
        if self._index < len(self._responses):
            content = self._responses[self._index]
            self._index += 1
        else:
            content = '```python\ndef solve(*args, **kwargs):\n    return None\n```'
        return LLMResponse(content=content, input_tokens=100, output_tokens=200)


@dataclass
class ExecutionContext:
    work_dir: Path
    knobs: dict[str, Any] = field(default_factory=dict)
    task: dict[str, Any] = field(default_factory=dict)
    budget_limit: int = 50
    llm_client: Any = None
    iteration: int = 0
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def read_json(self, filename: str) -> Any:
        p = self.work_dir / filename
        if p.exists():
            return json.loads(p.read_text())
        return None

    def write_json(self, filename: str, data: Any) -> None:
        p = self.work_dir / filename
        p.write_text(json.dumps(data, indent=2, default=str))

    def read_text(self, filename: str) -> str:
        p = self.work_dir / filename
        if p.exists():
            return p.read_text()
        return ""

    def write_text(self, filename: str, content: str) -> None:
        p = self.work_dir / filename
        p.write_text(content)


class WorkflowExecutor:
    def __init__(self, ctx: ExecutionContext):
        self.ctx = ctx
        self.log = structlog.get_logger().bind(run_id=ctx.run_id)

    def execute(self, node: Any) -> str | None:
        if isinstance(node, Loop):
            return self._execute_loop(node)
        elif isinstance(node, Sequential):
            return self._execute_sequential(node)
        elif isinstance(node, Parallel):
            return self._execute_parallel(node)
        elif isinstance(node, Conditional):
            return self._execute_conditional(node)
        elif isinstance(node, Package):
            return self._execute_package(node)
        elif isinstance(node, FnNode):
            return self._execute_fn(node)
        elif isinstance(node, LLMNode):
            return self._execute_llm(node)
        elif isinstance(node, AgentNode):
            return self._execute_agent(node)
        elif isinstance(node, GateNode):
            return self._execute_gate(node)
        return None

    def _execute_loop(self, loop: Loop) -> str | None:
        self.log.info("loop.start", name=loop.name, max_iterations=loop.max_iterations)
        for i in range(loop.max_iterations):
            self.ctx.iteration = i
            self.log.info("loop.iteration", name=loop.name, iteration=i)
            self.execute(loop.body)
            if loop.gate:
                result = self.execute(loop.gate)
                if result == "PROCEED":
                    self.log.info("loop.exit", name=loop.name, iteration=i, reason="gate_proceed")
                    return "PROCEED"
        self.log.info("loop.exit", name=loop.name, reason="max_iterations")
        return "PROCEED"

    def _execute_sequential(self, seq: Sequential) -> str | None:
        self.log.debug("sequential.start", name=seq.name)
        for child in seq.children:
            self.execute(child)
        return None

    def _execute_parallel(self, par: Parallel) -> str | None:
        self.log.debug("parallel.start", name=par.name)
        for child in par.children:
            self.execute(child)
        return None

    def _execute_conditional(self, cond: Conditional) -> str | None:
        self.log.debug("conditional.start", name=cond.name)
        result = self.execute(cond.gate) if cond.gate else "PROCEED"
        branch = cond.branches.get(result)
        if branch:
            self.log.info("conditional.branch", name=cond.name, decision=result)
            self._propagate_branch_state(branch)
            self.execute(branch)
        else:
            self.log.warning("conditional.no_branch", name=cond.name, decision=result)
        return result

    def _propagate_branch_state(self, node: Any) -> None:
        if isinstance(node, Package):
            for knob in node.knobs:
                self.ctx.knobs.setdefault(knob.name, knob.default)
        if isinstance(node, (Package, Sequential)):
            children = node.nodes if isinstance(node, Package) else node.children
            for child in children:
                self._propagate_branch_state(child)
        elif isinstance(node, Conditional):
            for branch in node.branches.values():
                self._propagate_branch_state(branch)
        elif isinstance(node, Loop):
            if node.body:
                self._propagate_branch_state(node.body)

    def _execute_package(self, pkg: Package) -> str | None:
        self.log.debug("package.start", name=pkg.name)
        for node in pkg.nodes:
            self.execute(node)
        return None

    def _execute_fn(self, fn: FnNode) -> str | None:
        self.log.info("fn.execute", name=fn.name, callable=fn.callable_name)
        self.ctx._current_node_reads = fn.reads
        self.ctx._current_node_writes = fn.writes
        module_path, func_name = fn.callable_name.split(":")
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        func(self.ctx)
        return None

    def _execute_llm(self, llm: LLMNode) -> str | None:
        self.log.info("llm.execute", name=llm.name, model=llm.model)
        prompt_parts = []
        for f in llm.reads:
            content = self.ctx.read_text(f)
            if content:
                prompt_parts.append(content)
        user_prompt = "\n\n".join(prompt_parts)

        temperature = self.ctx.knobs.get("temperature", llm.temperature)
        response = self.ctx.llm_client.generate(
            system_prompt=llm.system_prompt,
            user_prompt=user_prompt,
            model=llm.model,
            temperature=temperature,
        )

        code = extract_code_block(response.content)

        for f in llm.writes:
            self.ctx.write_text(f, code)

        from srf.ops.common.budget import record_llm_call
        from srf.ops.common.tracing import log_llm_call

        record_llm_call(self.ctx, response.input_tokens, response.output_tokens)
        log_llm_call(self.ctx, llm.name, llm.model, response.input_tokens, response.output_tokens)
        return None

    def _execute_agent(self, agent: AgentNode) -> str | None:
        from srf.agent_executor import execute_agent

        return execute_agent(self.ctx, agent, self.log)

    def _execute_gate(self, gate: GateNode) -> str:
        self.log.debug("gate.execute", name=gate.name, command=gate.evaluator_command)
        env = os.environ.copy()
        abs_work_dir = str(self.ctx.work_dir.resolve())
        env["SRF_WORK_DIR"] = abs_work_dir
        result = subprocess.run(
            [sys.executable] + gate.evaluator_command.split()[1:],
            capture_output=True,
            text=True,
            cwd=abs_work_dir,
            env=env,
            timeout=30,
        )
        decision = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else "PROCEED"
        self.log.info("gate.result", name=gate.name, decision=decision)

        from srf.ops.common.tracing import log_policy_decision
        log_policy_decision(self.ctx, decision, f"gate:{gate.name}")

        return decision
