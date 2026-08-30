"""AIDE action gate — reads aide_action.txt and returns the decision."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def action() -> None:
    work_dir = Path(os.environ.get("SRF_WORK_DIR", "."))
    action_path = work_dir / "aide_action.txt"
    if action_path.exists():
        decision = action_path.read_text().strip()
    else:
        decision = "DRAFT"
    print(decision)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "action":
        action()
    else:
        print("Usage: python -m srf.ops.aide.gate action", file=sys.stderr)
        sys.exit(1)
