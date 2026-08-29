"""Seed solution: simple greedy packing placing circles by decreasing radius."""
import math


def solve(n: int, radii: list[float]) -> list[tuple[float, float]]:
    sorted_indices = sorted(range(n), key=lambda i: radii[i], reverse=True)
    centers: list[tuple[float, float]] = [None] * n  # type: ignore
    placed: list[tuple[float, float, float]] = []

    for idx in sorted_indices:
        r = radii[idx]
        best_pos = None
        best_score = float("inf")

        for gx in range(10):
            for gy in range(10):
                x = r + (1.0 - 2 * r) * gx / 9
                y = r + (1.0 - 2 * r) * gy / 9

                valid = True
                min_gap = float("inf")
                for px, py, pr in placed:
                    dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
                    gap = dist - r - pr
                    if gap < -1e-9:
                        valid = False
                        break
                    min_gap = min(min_gap, gap)

                if valid:
                    score = -min_gap if placed else 0
                    if score < best_score:
                        best_score = score
                        best_pos = (x, y)

        if best_pos is None:
            best_pos = (r, r)

        centers[idx] = best_pos
        placed.append((best_pos[0], best_pos[1], r))

    return centers
