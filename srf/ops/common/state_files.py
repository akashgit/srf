"""Mode-to-state-file mapping, shared by CLI and Lab Director."""

from __future__ import annotations

STATE_FILES: dict[str, str] = {
    "gepa": "gepa_state.json",
    "best_of_n": "best_of_n_result.json",
    "scs": "scs_state.json",
    "aide": "aide_state.json",
    "ai_sci_v1": "autoresearch_state.json",
    "ai_sci_v2": "aide_state.json",
    "openevolve": "openevolve_state.json",
    "shinka": "shinka_state.json",
    "adaevolve": "adaevolve_state.json",
    "evox": "evox_state.json",
    "autoresearch": "autoresearch_state.json",
    "karpathy": "karpathy_state.json",
    "autoscientists": "autoscientists_state.json",
}

MODES_WITH_GEPA_STATE = {k for k in STATE_FILES if k != "best_of_n"}
