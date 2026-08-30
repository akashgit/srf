"""Island migration for multi-island evolutionary modes."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()


def ring_migrate(islands: list[list[dict[str, Any]]], migration_rate: float = 0.1) -> list[list[dict[str, Any]]]:
    """Ring-topology migration: island k sends best to island (k+1) % K."""
    if len(islands) < 2:
        return islands

    migrants: list[dict[str, Any] | None] = []
    for island in islands:
        if island:
            best = max(island, key=lambda p: p.get("score", 0.0))
            migrants.append(best)
        else:
            migrants.append(None)

    for i, migrant in enumerate(migrants):
        if migrant is not None:
            target = (i + 1) % len(islands)
            islands[target].append(migrant)
            logger.debug("migration.ring", from_island=i, to_island=target,
                         score=migrant.get("score", 0.0))

    return islands


def should_migrate(generation: int, interval: int = 10) -> bool:
    return generation > 0 and generation % interval == 0
