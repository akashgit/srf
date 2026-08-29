"""Circle packing evaluator.

Validates: no overlaps (pairwise distance > r_i + r_j),
no boundary violations (all circles within [0,1]^2),
computes sum of placed radii as score.
"""
import json
import math
import sys


def evaluate():
    try:
        from candidate import solve
    except ImportError:
        try:
            from initial import solve
        except ImportError:
            print(json.dumps({"score": 0.0, "metrics": {"error": "no solve function found"}}))
            return

    n = 26
    radii = [0.05 + 0.005 * i for i in range(n)]

    try:
        centers = solve(n, radii)
    except Exception as e:
        print(json.dumps({"score": 0.0, "metrics": {"error": str(e)[:200]}}))
        return

    if not centers or len(centers) != n:
        print(json.dumps({"score": 0.0, "metrics": {"error": f"expected {n} centers, got {len(centers) if centers else 0}"}}))
        return

    placed = []
    overlaps = 0
    boundary_violations = 0

    for i in range(n):
        x, y = centers[i]
        r = radii[i]

        if x - r < -1e-9 or x + r > 1.0 + 1e-9 or y - r < -1e-9 or y + r > 1.0 + 1e-9:
            boundary_violations += 1
            continue

        overlap_found = False
        for j, (px, py, pr) in enumerate(placed):
            dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
            if dist < r + pr - 1e-9:
                overlap_found = True
                overlaps += 1
                break

        if not overlap_found:
            placed.append((x, y, r))

    score = sum(r for _, _, r in placed)
    coverage = len(placed) / n if n > 0 else 0.0

    print(json.dumps({
        "score": round(score, 6),
        "metrics": {
            "coverage": round(coverage, 4),
            "overlaps": overlaps,
            "boundary_violations": boundary_violations,
            "placed": len(placed),
            "total": n,
        },
    }))


if __name__ == "__main__":
    evaluate()
