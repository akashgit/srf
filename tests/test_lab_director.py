"""Tests for Lab Director (#5) and MAP-Elites outer loop (#6)."""

from srf.lab.map_elites import (
    ImprovementEmitter,
    MAPElitesCell,
    MAPElitesGrid,
    MAPElitesLoop,
    RandomEmitter,
    compute_features,
)


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


