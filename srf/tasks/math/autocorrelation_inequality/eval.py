"""Autocorrelation inequality evaluator.

Verifies the proposed bound C by testing against random vectors.
Score = 1/C (tighter bound = higher score, since we want smaller C).
"""
import json
import math
import random
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

    n = 20
    try:
        C = solve(n)
    except Exception as e:
        print(json.dumps({"score": 0.0, "metrics": {"error": str(e)[:200]}}))
        return

    if not isinstance(C, (int, float)) or C <= 0:
        print(json.dumps({"score": 0.0, "metrics": {"error": f"invalid bound: {C}"}}))
        return

    random.seed(42)
    violations = 0
    max_ratio = 0.0
    num_tests = 1000

    for _ in range(num_tests):
        x = [random.gauss(0, 1) for _ in range(n)]
        energy = sum(xi ** 2 for xi in x)
        if energy < 1e-12:
            continue

        for k in range(1, n):
            autocorr = sum(x[i] * x[i + k] for i in range(n - k))
            ratio = autocorr / energy if energy > 0 else 0
            max_ratio = max(max_ratio, ratio)
            if ratio > C + 1e-9:
                violations += 1

    is_valid = violations == 0
    tightness = max_ratio / C if C > 0 else 0
    score = (1.0 / C) if is_valid else 0.0

    print(json.dumps({
        "score": round(score, 6),
        "metrics": {
            "bound": round(C, 6),
            "valid": is_valid,
            "violations": violations,
            "max_ratio": round(max_ratio, 6),
            "tightness": round(tightness, 4),
        },
    }))


if __name__ == "__main__":
    evaluate()
