"""Merge candidate selection — find_triplet_or_top2 from genealogy graph."""

from __future__ import annotations

from typing import Any

import structlog

from srf.ops.gepa.state import load_state, save_state

logger = structlog.get_logger()


def find_triplet_or_top2(ctx: Any) -> None:
    """Search genealogy for a valid (i, j, ancestor) triplet; fall back to top-2 by score.

    Reads: population.json, genealogy.json, gepa_state.json
    Writes: merge_candidates.json, selected_parent.json, gepa_state.json
    """
    population = ctx.read_json("population.json") or {}
    genealogy = ctx.read_json("genealogy.json") or {"nodes": {}, "edges": []}

    state = load_state(ctx)
    state.last_action = "merge"
    state.merge_attempts += 1
    save_state(ctx, state)

    if len(population) < 2:
        logger.warning("merge.insufficient_population", size=len(population))
        top = list(population.values())
        ctx.write_json("merge_candidates.json", top)
        if top:
            _write_merge_parent(ctx, top)
        return

    individuals = list(population.values())
    triplet = _find_triplet(individuals, genealogy)

    if triplet:
        ctx.write_json("merge_candidates.json", triplet)
        _write_merge_parent(ctx, triplet)
        logger.info(
            "merge.triplet_found",
            ids=[c["id"] for c in triplet],
        )
    else:
        top2 = _top_n_by_score(individuals, 2)
        ctx.write_json("merge_candidates.json", top2)
        _write_merge_parent(ctx, top2)
        logger.info(
            "merge.fallback_top2",
            ids=[c["id"] for c in top2],
        )


def _write_merge_parent(ctx: Any, candidates: list[dict]) -> None:
    """Write the best-scoring merge candidate as selected_parent.json."""
    best = max(candidates, key=lambda c: c.get("score", 0.0))
    ctx.write_json("selected_parent.json", {
        "id": best.get("id", "unknown"),
        "code": best.get("code", ""),
        "score": best.get("score", 0.0),
        "metrics": best.get("metrics", {}),
    })


def _find_triplet(individuals: list[dict], genealogy: dict) -> list[dict] | None:
    """Find (i, j, ancestor) where ancestor is a common ancestor of i and j."""
    edges = genealogy.get("edges", [])
    parent_map: dict[str, str] = {}
    for edge in edges:
        child = edge.get("child") or edge.get("target", "")
        parent = edge.get("parent") or edge.get("source", "")
        if child and parent:
            parent_map[child] = parent

    id_to_ind = {ind["id"]: ind for ind in individuals}

    for i in individuals:
        i_ancestors = _get_ancestors(i["id"], parent_map)
        for j in individuals:
            if j["id"] == i["id"]:
                continue
            j_ancestors = _get_ancestors(j["id"], parent_map)
            common = i_ancestors & j_ancestors
            for ancestor_id in common:
                if ancestor_id in id_to_ind:
                    return [i, j, id_to_ind[ancestor_id]]
    return None


def _get_ancestors(node_id: str, parent_map: dict[str, str], max_depth: int = 10) -> set[str]:
    ancestors = set()
    current = node_id
    for _ in range(max_depth):
        parent = parent_map.get(current)
        if not parent or parent in ancestors:
            break
        ancestors.add(parent)
        current = parent
    return ancestors


def _top_n_by_score(individuals: list[dict], n: int) -> list[dict]:
    sorted_inds = sorted(individuals, key=lambda x: x.get("score", 0.0), reverse=True)
    seen_codes = set()
    result = []
    for ind in sorted_inds:
        code_hash = hash(ind.get("code", ""))
        if code_hash not in seen_codes:
            seen_codes.add(code_hash)
            result.append(ind)
        if len(result) >= n:
            break
    return result
