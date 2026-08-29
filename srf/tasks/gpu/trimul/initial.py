"""Seed solution: naive O(n^3) triple product via numpy."""
import numpy as np


def solve(A: np.ndarray, B: np.ndarray, C: np.ndarray) -> np.ndarray:
    """Compute A @ B @ C."""
    return A @ B @ C
