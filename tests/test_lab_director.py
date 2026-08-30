"""Tests for Lab Director (#5) and MAP-Elites outer loop (#6)."""

from srf._factory_shim import MockLLMClient
from srf.lab.director import LabDirector
from srf.lab.map_elites import (
    ImprovementEmitter,
    MAPElitesCell,
    MAPElitesGrid,
    MAPElitesLoop,
    RandomEmitter,
    compute_features,
)
from srf.lab.protocol import LabDirectorProtocol, ModeResult


class TestLabDirector:
    def test_implements_protocol(self):
        director = LabDirector()
        assert isinstance(director, LabDirectorProtocol)

    def test_select_mode(self):
        director = LabDirector()
        mode = director.select_mode({"name": "test"})
        assert isinstance(mode, str)
        assert len(mode) > 0

    def test_compare_results(self):
        director = LabDirector()
        from pathlib import Path
        results = [
            ModeResult(score=0.5, best_code="a", trace_path=Path("."), cost=0.0),
            ModeResult(score=0.8, best_code="b", trace_path=Path("."), cost=0.0),
            ModeResult(score=0.3, best_code="c", trace_path=Path("."), cost=0.0),
        ]
        winner = director.compare_results(results)
        assert winner.score == 0.8

    def test_compare_empty(self):
        director = LabDirector()
        winner = director.compare_results([])
        assert winner.score == 0.0

    def test_run_mode_unknown(self):
        director = LabDirector()
        result = director.run_mode("nonexistent", {"name": "test"}, 10)
        assert result.score == 0.0

    def test_run_lab(self):
        director = LabDirector(llm_client=MockLLMClient())
        report = director.run_lab("circle_packing", ["gepa"], 10)
        assert "task" in report
        assert report["task"] == "circle_packing"
        assert "modes" in report
        assert "gepa" in report["modes"]

    def test_run_lab_unknown_task(self):
        director = LabDirector()
        report = director.run_lab("nonexistent", ["gepa"], 10)
        assert "error" in report

    def test_error_isolation(self):
        director = LabDirector(llm_client=MockLLMClient())
        # Even if one mode has issues, the lab should not crash
        report = director.run_lab("circle_packing", ["gepa", "nonexistent_mode"], 20)
        # Should complete without exception
        assert "modes" in report


class TestMAPElitesGrid:
    def test_empty_grid(self):
        grid = MAPElitesGrid()
        assert grid.coverage() == 0.0
        assert grid.best_cell() is None

    def test_update_cell(self):
        grid = MAPElitesGrid()
        cell = MAPElitesCell(mode="gepa", knob_values={"temperature": 0.7}, score=0.5, features=(0, 0, 0))
        updated = grid.update(cell)
        assert updated is True
        assert grid.best_cell().score == 0.5

    def test_update_with_better_score(self):
        grid = MAPElitesGrid()
        cell1 = MAPElitesCell(mode="gepa", knob_values={}, score=0.5, features=(0, 0, 0))
        cell2 = MAPElitesCell(mode="aide", knob_values={}, score=0.8, features=(0, 0, 0))
        grid.update(cell1)
        grid.update(cell2)
        assert grid.cells[(0, 0, 0)].score == 0.8

    def test_update_with_worse_score(self):
        grid = MAPElitesGrid()
        cell1 = MAPElitesCell(mode="gepa", knob_values={}, score=0.8, features=(0, 0, 0))
        cell2 = MAPElitesCell(mode="aide", knob_values={}, score=0.3, features=(0, 0, 0))
        grid.update(cell1)
        updated = grid.update(cell2)
        assert updated is False
        assert grid.cells[(0, 0, 0)].score == 0.8

    def test_coverage(self):
        grid = MAPElitesGrid(dims=(2, 2, 2))
        for i in range(2):
            for j in range(2):
                grid.update(MAPElitesCell(mode="gepa", knob_values={}, score=0.5, features=(i, j, 0)))
        assert grid.coverage() == 4 / 8


class TestMAPElitesLoop:
    def test_suggest(self):
        loop = MAPElitesLoop(
            modes=["gepa", "aide"],
            knob_specs={"temperature": [0.3, 0.7, 0.9]},
        )
        mode, knobs = loop.suggest()
        assert mode in ("gepa", "aide")
        assert "temperature" in knobs

    def test_report_and_results(self):
        loop = MAPElitesLoop(
            modes=["gepa", "aide"],
            knob_specs={"temperature": [0.3, 0.7, 0.9]},
        )
        loop.report("gepa", {"temperature": 0.7}, 0.5, 20)
        results = loop.get_results()
        assert results["n_cells"] == 1
        assert results["best"]["score"] == 0.5

    def test_improvement_emitter(self):
        grid = MAPElitesGrid()
        grid.update(MAPElitesCell(mode="gepa", knob_values={"temperature": 0.7}, score=0.5, features=(0, 0, 0)))
        emitter = ImprovementEmitter(grid, {"temperature": [0.3, 0.7, 0.9]})
        result = emitter.emit()
        assert result is not None
        mode, knobs = result
        assert mode == "gepa"

    def test_random_emitter(self):
        emitter = RandomEmitter(["gepa", "aide"], {"temperature": [0.3, 0.7]})
        mode, knobs = emitter.emit()
        assert mode in ("gepa", "aide")


class TestComputeFeatures:
    def test_features(self):
        features = compute_features("gepa", {"parent_selection": "best"}, 30)
        assert len(features) == 3
        assert features[0] == 0  # archive type
        assert features[1] == 0  # best strategy
        assert features[2] == 1  # mid budget

    def test_tree_search_type(self):
        features = compute_features("aide", {}, 10)
        assert features[0] == 1  # tree type

    def test_high_budget(self):
        features = compute_features("gepa", {}, 100)
        assert features[2] == 2  # high budget


class TestCLISubcommands:
    def test_lab_command_parses(self):
        from srf.cli import main
        # Just test that the CLI doesn't crash with --mock-llm
        result = main(["lab", "--task", "circle_packing", "--modes", "gepa", "--budget", "5", "--mock-llm"])
        assert result == 0

    def test_evolve_command_parses(self):
        from srf.cli import main
        result = main(["evolve", "--task", "circle_packing", "--generations", "2", "--budget", "10", "--mock-llm"])
        assert result == 0
