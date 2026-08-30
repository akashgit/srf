"""AdaEvolve meta-strategy gate."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def meta_gate() -> None:
    work_dir = Path(os.environ.get("SRF_WORK_DIR", "."))
    decision_path = work_dir / "meta_decision.txt"
    if decision_path.exists():
        print(decision_path.read_text().strip())
    else:
        print("NORMAL")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "meta_gate":
        meta_gate()
    else:
        print("Usage: python -m srf.ops.adaevolve.gate meta_gate", file=sys.stderr)
        sys.exit(1)
