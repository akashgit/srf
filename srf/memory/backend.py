"""MemoryBackend — SQLite persistence for cross-iteration and cross-run learning."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS solutions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    task_hash TEXT NOT NULL,
    code TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0.0,
    metrics TEXT DEFAULT '{}',
    error TEXT,
    iteration INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    parent_id TEXT,
    mode TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id TEXT NOT NULL,
    child_id TEXT NOT NULL,
    relation TEXT DEFAULT 'mutation',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    task_hash TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT 'reflection',
    score_delta REAL DEFAULT 0.0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    task_hash TEXT NOT NULL,
    mode TEXT NOT NULL,
    best_score REAL DEFAULT 0.0,
    total_evals INTEGER DEFAULT 0,
    started_at REAL NOT NULL,
    finished_at REAL
);

CREATE INDEX IF NOT EXISTS idx_solutions_task ON solutions(task_hash);
CREATE INDEX IF NOT EXISTS idx_solutions_run ON solutions(run_id);
CREATE INDEX IF NOT EXISTS idx_solutions_score ON solutions(score DESC);
CREATE INDEX IF NOT EXISTS idx_lineage_parent ON lineage(parent_id);
CREATE INDEX IF NOT EXISTS idx_lineage_child ON lineage(child_id);
CREATE INDEX IF NOT EXISTS idx_insights_task ON insights(task_hash);
"""


@dataclass
class Solution:
    id: str
    run_id: str
    task_hash: str
    code: str
    score: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    iteration: int = 0
    created_at: float = 0.0
    parent_id: str | None = None
    mode: str = ""


class MemoryBackend:
    def __init__(self, db_path: Path | str = "memory.db"):
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._init_db()
        return self._conn  # type: ignore

    def store_solution(self, sol: Solution) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO solutions
               (id, run_id, task_hash, code, score, metrics, error, iteration, created_at, parent_id, mode)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sol.id, sol.run_id, sol.task_hash, sol.code, sol.score,
             json.dumps(sol.metrics), sol.error, sol.iteration,
             sol.created_at or time.time(), sol.parent_id, sol.mode),
        )
        if sol.parent_id:
            self.conn.execute(
                "INSERT INTO lineage (parent_id, child_id, relation, created_at) VALUES (?, ?, ?, ?)",
                (sol.parent_id, sol.id, "mutation", time.time()),
            )
        self.conn.commit()

    def get_solution(self, sol_id: str) -> Solution | None:
        row = self.conn.execute("SELECT * FROM solutions WHERE id = ?", (sol_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_solution(row)

    def list_solutions(self, task_hash: str | None = None, run_id: str | None = None,
                       limit: int = 100, order_by_score: bool = True) -> list[Solution]:
        query = "SELECT * FROM solutions WHERE 1=1"
        params: list[Any] = []
        if task_hash:
            query += " AND task_hash = ?"
            params.append(task_hash)
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        if order_by_score:
            query += " ORDER BY score DESC"
        query += " LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_solution(r) for r in rows]

    def delete_solution(self, sol_id: str) -> bool:
        cursor = self.conn.execute("DELETE FROM solutions WHERE id = ?", (sol_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def get_lineage_chain(self, sol_id: str, max_depth: int = 50) -> list[str]:
        chain = [sol_id]
        current = sol_id
        for _ in range(max_depth):
            row = self.conn.execute(
                "SELECT parent_id FROM lineage WHERE child_id = ? LIMIT 1", (current,)
            ).fetchone()
            if row is None or row["parent_id"] is None:
                break
            chain.append(row["parent_id"])
            current = row["parent_id"]
        return list(reversed(chain))

    def store_insight(self, run_id: str, task_hash: str, content: str,
                      source: str = "reflection", score_delta: float = 0.0) -> None:
        self.conn.execute(
            "INSERT INTO insights (run_id, task_hash, content, source, score_delta, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, task_hash, content, source, score_delta, time.time()),
        )
        self.conn.commit()

    def get_insights(self, task_hash: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM insights WHERE task_hash = ? ORDER BY created_at DESC LIMIT ?",
            (task_hash, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def register_run(self, run_id: str, task_hash: str, mode: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, task_hash, mode, started_at) VALUES (?, ?, ?, ?)",
            (run_id, task_hash, mode, time.time()),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, best_score: float, total_evals: int) -> None:
        self.conn.execute(
            "UPDATE runs SET best_score = ?, total_evals = ?, finished_at = ? WHERE run_id = ?",
            (best_score, total_evals, time.time(), run_id),
        )
        self.conn.commit()

    def evict(self, task_hash: str, keep_top_n: int = 50) -> int:
        """Evict low-scoring solutions, preserving the best and their lineage."""
        best = self.conn.execute(
            "SELECT id FROM solutions WHERE task_hash = ? ORDER BY score DESC LIMIT 1",
            (task_hash,),
        ).fetchone()
        best_id = best["id"] if best else None

        protected = set()
        if best_id:
            protected = set(self.get_lineage_chain(best_id))

        all_ids = [
            r["id"] for r in self.conn.execute(
                "SELECT id FROM solutions WHERE task_hash = ? ORDER BY score DESC",
                (task_hash,),
            ).fetchall()
        ]

        to_keep = set(all_ids[:keep_top_n]) | protected
        to_delete = [sid for sid in all_ids if sid not in to_keep]

        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            self.conn.execute(f"DELETE FROM solutions WHERE id IN ({placeholders})", to_delete)
            self.conn.commit()

        return len(to_delete)

    def _row_to_solution(self, row: sqlite3.Row) -> Solution:
        return Solution(
            id=row["id"],
            run_id=row["run_id"],
            task_hash=row["task_hash"],
            code=row["code"],
            score=row["score"],
            metrics=json.loads(row["metrics"]) if row["metrics"] else {},
            error=row["error"],
            iteration=row["iteration"],
            created_at=row["created_at"],
            parent_id=row["parent_id"],
            mode=row["mode"],
        )


def task_hash(task_config: dict[str, Any]) -> str:
    key = f"{task_config.get('name', '')}:{task_config.get('category', '')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def build_memory_context(backend: MemoryBackend, task_hash_val: str,
                         token_budget: int = 4000) -> str:
    """Assemble token-budgeted context from memory for LLM prompts."""
    parts: list[str] = []
    char_budget = token_budget * 4

    best_budget = int(char_budget * 0.40)
    best_solutions = backend.list_solutions(task_hash=task_hash_val, limit=5)
    best_section = []
    chars = 0
    for sol in best_solutions:
        entry = f"Score {sol.score:.4f}:\n```python\n{sol.code[:500]}\n```\n"
        if chars + len(entry) > best_budget:
            break
        best_section.append(entry)
        chars += len(entry)
    if best_section:
        parts.append("## Best Solutions\n" + "\n".join(best_section))

    insight_budget = int(char_budget * 0.25)
    insights = backend.get_insights(task_hash_val, limit=10)
    insight_section = []
    chars = 0
    for ins in insights:
        entry = f"- {ins['content'][:200]}"
        if chars + len(entry) > insight_budget:
            break
        insight_section.append(entry)
        chars += len(entry)
    if insight_section:
        parts.append("## Insights\n" + "\n".join(insight_section))

    failure_budget = int(char_budget * 0.25)
    failures = backend.list_solutions(task_hash=task_hash_val, limit=20)
    error_solutions = [s for s in failures if s.error][:5]
    failure_section = []
    chars = 0
    for sol in error_solutions:
        entry = f"- Score {sol.score:.4f}: {sol.error[:150]}"
        if chars + len(entry) > failure_budget:
            break
        failure_section.append(entry)
        chars += len(entry)
    if failure_section:
        parts.append("## Recent Failures\n" + "\n".join(failure_section))

    return "\n\n".join(parts) if parts else ""
