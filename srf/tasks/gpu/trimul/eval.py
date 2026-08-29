"""Triple matrix multiplication evaluator.

Correctness check against numpy reference + timing measurement.
"""
import json
import sys
import time

import numpy as np


def evaluate():
    try:
        from candidate import solve
    except ImportError:
        try:
            from initial import solve
        except ImportError:
            print(json.dumps({"score": 0.0, "metrics": {"error": "no solve function found"}}))
            return

    np.random.seed(42)
    n = 128
    A = np.random.randn(n, n)
    B = np.random.randn(n, n)
    C = np.random.randn(n, n)

    reference = A @ B @ C

    try:
        start = time.perf_counter()
        result = solve(A, B, C)
        elapsed = time.perf_counter() - start
    except Exception as e:
        print(json.dumps({"score": 0.0, "metrics": {"error": str(e)[:200]}}))
        return

    if result is None or not isinstance(result, np.ndarray):
        print(json.dumps({"score": 0.0, "metrics": {"error": "solve returned non-array"}}))
        return

    if result.shape != reference.shape:
        print(json.dumps({"score": 0.0, "metrics": {"error": f"shape mismatch: {result.shape} vs {reference.shape}"}}))
        return

    max_err = float(np.max(np.abs(result - reference)))
    rel_err = max_err / (np.linalg.norm(reference) + 1e-12)

    correct = bool(rel_err < 1e-6)

    ref_start = time.perf_counter()
    _ = A @ B @ C
    ref_elapsed = time.perf_counter() - ref_start

    speedup = ref_elapsed / max(elapsed, 1e-9)
    score = speedup if correct else 0.0

    print(json.dumps({
        "score": round(score, 6),
        "metrics": {
            "correct": correct,
            "relative_error": round(rel_err, 10),
            "elapsed_s": round(elapsed, 6),
            "reference_s": round(ref_elapsed, 6),
            "speedup": round(speedup, 4),
        },
    }))


if __name__ == "__main__":
    evaluate()
