"""Integration tests for execute_agent (AgentNode execution)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from srf._factory_shim import AgentNode, ExecutionContext, LLMResponse, MockLLMClient


def _make_ctx(work_dir=None, llm_client=None):
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp())
    ctx = ExecutionContext(
        work_dir=work_dir,
        knobs={},
        task={"name": "test"},
        budget_limit=50,
        llm_client=llm_client or MockLLMClient(),
    )
    (work_dir / "budget_state.json").write_text(json.dumps({
        "eval_count": 0, "llm_input_tokens": 0,
        "llm_output_tokens": 0, "llm_calls": 0, "budget_limit": 50,
    }))
    (work_dir / "trace.jsonl").write_text("")
    return ctx


class TestExecuteAgentIntegration:
    def test_reads_input_writes_output(self):
        """AgentNode reads from input files, calls LLM, writes extracted code to output files."""
        from srf.agent_executor import execute_agent

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _make_ctx(
                work_dir=Path(tmpdir),
                llm_client=MockLLMClient(responses=[
                    "Here is the solution:\n```python\ndef solve(x):\n    return x + 1\n```"
                ]),
            )
            ctx.write_text("task_prompt.txt", "Solve this problem")

            agent = AgentNode(
                name="test_agent",
                model="sonnet",
                system_prompt="You are a helpful assistant.",
                reads={"task_prompt.txt"},
                writes={"candidate.py"},
            )

            result = execute_agent(ctx, agent)
            assert result is None

            output = ctx.read_text("candidate.py")
            assert "def solve(x):" in output
            assert "return x + 1" in output

    def test_multi_file_read(self):
        """AgentNode reads from multiple input files and concatenates them."""
        from srf.agent_executor import execute_agent

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_client = MagicMock()
            mock_client.generate.return_value = LLMResponse(
                content="```python\nresult = 42\n```",
                input_tokens=50,
                output_tokens=100,
            )

            ctx = _make_ctx(work_dir=Path(tmpdir), llm_client=mock_client)
            ctx.write_text("context.txt", "Context info")
            ctx.write_text("instructions.txt", "Do the thing")

            agent = AgentNode(
                name="multi_reader",
                model="haiku",
                system_prompt="system",
                reads={"context.txt", "instructions.txt"},
                writes={"output.py"},
            )

            execute_agent(ctx, agent)

            call_args = mock_client.generate.call_args
            user_prompt = call_args.kwargs.get("user_prompt") or call_args[1].get("user_prompt") or call_args[0][1]
            assert "Context info" in user_prompt
            assert "Do the thing" in user_prompt

    def test_budget_and_trace_recorded(self):
        """AgentNode execution records LLM token usage in budget and trace."""
        from srf.agent_executor import execute_agent
        from srf.ops.common.tracing import init_trace_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _make_ctx(
                work_dir=Path(tmpdir),
                llm_client=MockLLMClient(),
            )
            init_trace_dir(Path(tmpdir))

            agent = AgentNode(
                name="budget_test",
                model="sonnet",
                system_prompt="test",
                reads=set(),
                writes={"out.py"},
            )

            execute_agent(ctx, agent)

            budget = ctx.read_json("budget_state.json")
            assert budget["llm_calls"] == 1
            assert budget["llm_input_tokens"] > 0
            assert budget["llm_output_tokens"] > 0

            trace_content = ctx.read_text("llm_calls.jsonl")
            assert "budget_test" in trace_content

    def test_empty_reads_produces_output(self):
        """AgentNode with no read files still produces output."""
        from srf.agent_executor import execute_agent

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _make_ctx(work_dir=Path(tmpdir))

            agent = AgentNode(
                name="no_reads",
                model="sonnet",
                system_prompt="Generate code",
                reads=set(),
                writes={"generated.py"},
            )

            execute_agent(ctx, agent)

            output = ctx.read_text("generated.py")
            assert len(output) > 0

    def test_workflow_executor_delegates_to_agent_executor(self):
        """WorkflowExecutor._execute_agent delegates to the extracted module."""
        from srf._factory_shim import WorkflowExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = _make_ctx(work_dir=Path(tmpdir))

            agent = AgentNode(
                name="delegation_test",
                model="sonnet",
                system_prompt="test",
                reads=set(),
                writes={"result.py"},
            )

            executor = WorkflowExecutor(ctx)
            executor.execute(agent)

            output = ctx.read_text("result.py")
            assert len(output) > 0
