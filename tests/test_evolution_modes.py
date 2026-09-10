"""Tests for evolution modes: OpenEvolve (#9), ShinkaEvolve (#19), AdaEvolve (#16), EvoX (#17)."""


from srf.ops.common.migration import ring_migrate, should_migrate
from srf.ops.common.reflection import analyze_stagnation, build_reflection_prompt


class TestMigration:
    def test_ring_migrate(self):
        islands = [
            [{"id": "a", "score": 0.5}],
            [{"id": "b", "score": 0.8}],
            [{"id": "c", "score": 0.3}],
        ]
        result = ring_migrate(islands)
        assert len(result) == 3
        # Island 1 should have received island 0's best
        assert any(p["id"] == "a" for p in result[1])

    def test_should_migrate(self):
        assert should_migrate(0, 10) is False
        assert should_migrate(10, 10) is True
        assert should_migrate(15, 10) is False
        assert should_migrate(20, 10) is True


class TestReflection:
    def test_analyze_stagnation_not_stagnating(self):
        history = [{"score": i * 0.1, "improved": True} for i in range(10)]
        result = analyze_stagnation(history)
        assert result["stagnating"] is False

    def test_analyze_stagnation_yes(self):
        history = [{"score": 0.5, "improved": False} for _ in range(10)]
        result = analyze_stagnation(history)
        assert result["stagnating"] is True

    def test_build_reflection_prompt(self):
        task = {"name": "test", "category": "math", "description": "test task"}
        history = [{"score": 0.5, "action": "mutate", "improved": True}]
        prompt = build_reflection_prompt(task, history)
        assert "test" in prompt
        assert "mutate" in prompt

    def test_insufficient_history(self):
        result = analyze_stagnation([{"score": 0.5}])
        assert result["stagnating"] is False
        assert result["reason"] == "insufficient_history"


