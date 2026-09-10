"""Unit tests for GEPA domain callables."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from srf.ops.gepa.acceptance import accept_or_reject
from srf.ops.gepa.decision import _decide
from srf.ops.gepa.merge import find_triplet_or_top2
from srf.ops.gepa.population import select_parent
from srf.ops.gepa.prompts import build_merge_prompt, build_reflective_prompt
from srf.ops.gepa.state import GEPAState


def _make_ctx(work_dir=None, knobs=None, task=None, budget=50):
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp())
    ctx = MagicMock()
    ctx.work_dir = work_dir
    ctx.knobs = knobs or {"parent_selection": "best", "max_rejection_context": 5, "acceptance_mode": "strict", "merge_stagnation_threshold": 15}
    ctx.task = task or {"name": "test", "description": "test task", "category": "test"}
    ctx.budget_limit = budget
    ctx.iteration = 0
    ctx.run_id = "test123"

    def read_json(name):
        p = work_dir / name
        return json.loads(p.read_text()) if p.exists() else None

    def write_json(name, data):
        (work_dir / name).write_text(json.dumps(data, default=str))

    def read_text(name):
        p = work_dir / name
        return p.read_text() if p.exists() else ""

    def write_text(name, content):
        (work_dir / name).write_text(content)

    ctx.read_json = read_json
    ctx.write_json = write_json
    ctx.read_text = read_text
    ctx.write_text = write_text
    return ctx


class TestSelectParent:
    def test_empty_population_uses_seed(self):
        ctx = _make_ctx(task={"initial_code": "def solve(): return 1"})
        ctx.write_json("population.json", {})
        ctx.write_json("gepa_state.json", GEPAState().model_dump())
        select_parent(ctx)
        result = ctx.read_json("selected_parent.json")
        assert result["id"] == "seed"

    def test_best_strategy(self):
        ctx = _make_ctx()
        population = {
            "a": {"id": "a", "code": "x=1", "score": 0.5},
            "b": {"id": "b", "code": "x=2", "score": 0.9},
        }
        ctx.write_json("population.json", population)
        ctx.write_json("gepa_state.json", GEPAState().model_dump())
        select_parent(ctx)
        result = ctx.read_json("selected_parent.json")
        assert result["id"] == "b"

    def test_pareto_strategy(self):
        ctx = _make_ctx(knobs={"parent_selection": "pareto"})
        population = {
            "a": {"id": "a", "code": "x", "score": 0.5},
            "b": {"id": "b", "code": "x" * 100, "score": 0.9},
        }
        ctx.write_json("population.json", population)
        ctx.write_json("gepa_state.json", GEPAState().model_dump())
        select_parent(ctx)
        result = ctx.read_json("selected_parent.json")
        assert result["id"] in ("a", "b")


class TestBuildReflectivePrompt:
    def test_basic_prompt(self):
        ctx = _make_ctx()
        ctx.write_json("selected_parent.json", {"id": "a", "code": "x=1", "score": 0.5, "metrics": {}})
        ctx.write_json("rejection_history.json", [])
        ctx.write_json("accepted_history.json", [])
        build_reflective_prompt(ctx)
        prompt = ctx.read_text("mutate_prompt.md")
        assert "x=1" in prompt
        assert "score: 0.5" in prompt

    def test_prompt_with_rejections(self):
        ctx = _make_ctx(knobs={"max_rejection_context": 3})
        ctx.write_json("selected_parent.json", {"id": "a", "code": "x=1", "score": 0.5, "metrics": {}})
        rejections = [
            {"score": 0.3, "parent_score": 0.5, "code": f"x={i}", "error": None, "metrics": {}}
            for i in range(5)
        ]
        ctx.write_json("rejection_history.json", rejections)
        ctx.write_json("accepted_history.json", [])
        build_reflective_prompt(ctx)
        prompt = ctx.read_text("mutate_prompt.md")
        assert "Rejected" in prompt


class TestBuildMergePrompt:
    def test_basic_merge_prompt(self):
        ctx = _make_ctx()
        candidates = [
            {"id": "a", "code": "x=1", "score": 0.5},
            {"id": "b", "code": "x=2", "score": 0.8},
        ]
        ctx.write_json("merge_candidates.json", candidates)
        build_merge_prompt(ctx)
        prompt = ctx.read_text("merge_prompt.md")
        assert "Program 1" in prompt
        assert "Program 2" in prompt


class TestFindMergeCandidates:
    def test_top2_fallback(self):
        ctx = _make_ctx()
        population = {
            "a": {"id": "a", "code": "x=1", "score": 0.5},
            "b": {"id": "b", "code": "x=2", "score": 0.9},
            "c": {"id": "c", "code": "x=3", "score": 0.3},
        }
        ctx.write_json("population.json", population)
        ctx.write_json("genealogy.json", {"nodes": {}, "edges": []})
        find_triplet_or_top2(ctx)
        result = ctx.read_json("merge_candidates.json")
        assert len(result) == 2
        assert result[0]["score"] >= result[1]["score"]

    def test_insufficient_population(self):
        ctx = _make_ctx()
        ctx.write_json("population.json", {"a": {"id": "a", "code": "x=1", "score": 0.5}})
        ctx.write_json("genealogy.json", {"nodes": {}, "edges": []})
        find_triplet_or_top2(ctx)
        result = ctx.read_json("merge_candidates.json")
        assert len(result) == 1


class TestShouldMerge:
    """The gate names its own forward outcomes: mutate or merge, never reloop."""

    def test_no_stagnation_returns_mutate(self):
        state = GEPAState(stagnation_counter=0, use_merge=True)
        decision, _ = _decide(state, {"a": {}, "b": {}}, 15)
        assert decision == "mutate"

    def test_stagnation_triggers_merge(self):
        state = GEPAState(stagnation_counter=15, use_merge=True)
        decision, _ = _decide(state, {"a": {}, "b": {}}, 15)
        assert decision == "merge"

    def test_merge_disabled(self):
        state = GEPAState(stagnation_counter=100, use_merge=False)
        decision, _ = _decide(state, {"a": {}, "b": {}}, 15)
        assert decision == "mutate"

    def test_population_too_small(self):
        state = GEPAState(stagnation_counter=20, use_merge=True)
        decision, _ = _decide(state, {"a": {}}, 15)
        assert decision == "mutate"

    def test_merge_attempts_exhausted(self):
        state = GEPAState(stagnation_counter=20, use_merge=True, merge_attempts=5)
        decision, _ = _decide(state, {"a": {}, "b": {}}, 15)
        assert decision == "mutate"


class TestAcceptOrReject:
    def test_strict_accept_improvement(self):
        ctx = _make_ctx()
        ctx.write_json("eval_result.json", {"score": 0.8, "metrics": {}, "error": None})
        ctx.write_text("candidate.py", "def solve(): return 2")
        ctx.write_json("selected_parent.json", {"id": "a", "code": "x=1", "score": 0.5, "metrics": {}})
        ctx.write_json("population.json", {"a": {"id": "a", "code": "x=1", "score": 0.5}})
        ctx.write_json("genealogy.json", {"nodes": {"a": {"generation": 0}}, "edges": []})
        ctx.write_json("gepa_state.json", GEPAState().model_dump())
        ctx.write_json("rejection_history.json", [])
        ctx.write_json("accepted_history.json", [])
        ctx.write_json("budget_state.json", {"eval_count": 0, "llm_input_tokens": 0, "llm_output_tokens": 0, "llm_calls": 0, "budget_limit": 50})

        accept_or_reject(ctx)

        state = ctx.read_json("gepa_state.json")
        assert state["best_score"] == 0.8
        assert state["total_accepted"] == 1

    def test_strict_reject_worse(self):
        ctx = _make_ctx()
        ctx.write_json("eval_result.json", {"score": 0.3, "metrics": {}, "error": None})
        ctx.write_text("candidate.py", "def solve(): return 0")
        ctx.write_json("selected_parent.json", {"id": "a", "code": "x=1", "score": 0.5, "metrics": {}})
        ctx.write_json("population.json", {"a": {"id": "a", "code": "x=1", "score": 0.5}})
        ctx.write_json("genealogy.json", {"nodes": {"a": {"generation": 0}}, "edges": []})
        ctx.write_json("gepa_state.json", GEPAState().model_dump())
        ctx.write_json("rejection_history.json", [])
        ctx.write_json("accepted_history.json", [])
        ctx.write_json("budget_state.json", {"eval_count": 0, "llm_input_tokens": 0, "llm_output_tokens": 0, "llm_calls": 0, "budget_limit": 50})

        accept_or_reject(ctx)

        state = ctx.read_json("gepa_state.json")
        assert state["total_rejected"] == 1
        rejections = ctx.read_json("rejection_history.json")
        assert len(rejections) == 1

    def test_lenient_accept(self):
        ctx = _make_ctx(knobs={"acceptance_mode": "lenient", "parent_selection": "best", "max_rejection_context": 5, "merge_stagnation_threshold": 15})
        ctx.write_json("eval_result.json", {"score": 0.48, "metrics": {}, "error": None})
        ctx.write_text("candidate.py", "def solve(): return 1")
        ctx.write_json("selected_parent.json", {"id": "a", "code": "x=1", "score": 0.5, "metrics": {}})
        ctx.write_json("population.json", {"a": {"id": "a", "code": "x=1", "score": 0.5}})
        ctx.write_json("genealogy.json", {"nodes": {"a": {"generation": 0}}, "edges": []})
        ctx.write_json("gepa_state.json", GEPAState().model_dump())
        ctx.write_json("rejection_history.json", [])
        ctx.write_json("accepted_history.json", [])
        ctx.write_json("budget_state.json", {"eval_count": 0, "llm_input_tokens": 0, "llm_output_tokens": 0, "llm_calls": 0, "budget_limit": 50})

        accept_or_reject(ctx)

        state = ctx.read_json("gepa_state.json")
        assert state["total_accepted"] == 1
