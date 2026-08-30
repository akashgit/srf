"""Tests for reflective memory database (Issue #7)."""

import tempfile
from pathlib import Path

from srf.memory.backend import (
    MemoryBackend,
    Solution,
    build_memory_context,
    task_hash,
)


def _make_backend():
    tmp = tempfile.mkdtemp()
    return MemoryBackend(db_path=Path(tmp) / "test_memory.db")


def test_create_tables():
    backend = _make_backend()
    tables = backend.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {r["name"] for r in tables}
    assert "solutions" in names
    assert "lineage" in names
    assert "insights" in names
    assert "runs" in names
    backend.close()


def test_store_and_get_solution():
    backend = _make_backend()
    sol = Solution(
        id="abc123", run_id="run1", task_hash="th1",
        code="def solve(): return 1", score=0.75,
    )
    backend.store_solution(sol)
    retrieved = backend.get_solution("abc123")
    assert retrieved is not None
    assert retrieved.score == 0.75
    assert retrieved.code == "def solve(): return 1"
    backend.close()


def test_list_solutions_by_task():
    backend = _make_backend()
    for i in range(5):
        backend.store_solution(Solution(
            id=f"sol_{i}", run_id="run1", task_hash="th1",
            code=f"x={i}", score=i * 0.1,
        ))
    backend.store_solution(Solution(
        id="other", run_id="run2", task_hash="th2",
        code="y=1", score=0.9,
    ))
    results = backend.list_solutions(task_hash="th1")
    assert len(results) == 5
    assert all(r.task_hash == "th1" for r in results)
    assert results[0].score >= results[-1].score
    backend.close()


def test_cross_run_retrieval():
    backend = _make_backend()
    backend.store_solution(Solution(id="s1", run_id="run1", task_hash="th1", code="x", score=0.5))
    backend.store_solution(Solution(id="s2", run_id="run2", task_hash="th1", code="y", score=0.8))
    results = backend.list_solutions(task_hash="th1")
    assert len(results) == 2
    run_ids = {r.run_id for r in results}
    assert run_ids == {"run1", "run2"}
    backend.close()


def test_delete_solution():
    backend = _make_backend()
    backend.store_solution(Solution(id="del1", run_id="r1", task_hash="th1", code="x", score=0.1))
    assert backend.delete_solution("del1") is True
    assert backend.get_solution("del1") is None
    assert backend.delete_solution("nonexistent") is False
    backend.close()


def test_lineage_chain():
    backend = _make_backend()
    backend.store_solution(Solution(id="root", run_id="r1", task_hash="th1", code="x", score=0.1))
    backend.store_solution(Solution(id="child1", run_id="r1", task_hash="th1", code="y", score=0.3, parent_id="root"))
    backend.store_solution(Solution(id="child2", run_id="r1", task_hash="th1", code="z", score=0.5, parent_id="child1"))
    chain = backend.get_lineage_chain("child2")
    assert chain == ["root", "child1", "child2"]
    backend.close()


def test_eviction_preserves_best_and_lineage():
    backend = _make_backend()
    backend.store_solution(Solution(id="s0", run_id="r1", task_hash="th1", code="a", score=0.1))
    backend.store_solution(Solution(id="s1", run_id="r1", task_hash="th1", code="b", score=0.5, parent_id="s0"))
    backend.store_solution(Solution(id="s2", run_id="r1", task_hash="th1", code="c", score=0.9, parent_id="s1"))
    for i in range(10):
        backend.store_solution(Solution(id=f"filler_{i}", run_id="r1", task_hash="th1", code=f"f{i}", score=0.05))

    evicted = backend.evict("th1", keep_top_n=3)
    assert evicted > 0

    # Best solution and its lineage must survive
    assert backend.get_solution("s2") is not None
    assert backend.get_solution("s1") is not None
    assert backend.get_solution("s0") is not None
    backend.close()


def test_store_and_get_insights():
    backend = _make_backend()
    backend.store_insight("r1", "th1", "Higher temperatures help exploration", score_delta=0.1)
    backend.store_insight("r1", "th1", "Avoid numpy vectorization bugs", score_delta=-0.05)
    insights = backend.get_insights("th1")
    assert len(insights) == 2
    contents = {i["content"] for i in insights}
    assert "Higher temperatures help exploration" in contents
    backend.close()


def test_register_and_finish_run():
    backend = _make_backend()
    backend.register_run("r1", "th1", "gepa")
    backend.finish_run("r1", best_score=0.85, total_evals=50)
    row = backend.conn.execute("SELECT * FROM runs WHERE run_id = ?", ("r1",)).fetchone()
    assert row is not None
    assert row["best_score"] == 0.85
    assert row["total_evals"] == 50
    assert row["finished_at"] is not None
    backend.close()


def test_build_memory_context():
    backend = _make_backend()
    backend.store_solution(Solution(id="best", run_id="r1", task_hash="th1", code="def solve(): return best()", score=0.9))
    backend.store_solution(Solution(id="err", run_id="r1", task_hash="th1", code="bad", score=0.0, error="runtime error"))
    backend.store_insight("r1", "th1", "Use dynamic programming")
    context = build_memory_context(backend, "th1", token_budget=4000)
    assert "Best Solutions" in context
    assert "solve" in context
    backend.close()


def test_build_memory_context_respects_budget():
    backend = _make_backend()
    for i in range(100):
        backend.store_solution(Solution(
            id=f"s{i}", run_id="r1", task_hash="th1",
            code="x" * 1000, score=i * 0.01,
        ))
    context = build_memory_context(backend, "th1", token_budget=500)
    assert len(context) < 500 * 4 + 200
    backend.close()


def test_task_hash_deterministic():
    config = {"name": "circle_packing", "category": "math"}
    h1 = task_hash(config)
    h2 = task_hash(config)
    assert h1 == h2
    assert len(h1) == 16


def test_persistence_across_instantiations():
    tmp = tempfile.mkdtemp()
    db_path = Path(tmp) / "persist.db"

    backend1 = MemoryBackend(db_path=db_path)
    backend1.store_solution(Solution(id="persist1", run_id="r1", task_hash="th1", code="x", score=0.5))
    backend1.close()

    backend2 = MemoryBackend(db_path=db_path)
    sol = backend2.get_solution("persist1")
    assert sol is not None
    assert sol.score == 0.5
    backend2.close()
