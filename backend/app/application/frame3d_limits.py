"""Single source of truth for the 3D frame model size limits.

Used by the chat parser, the Quick-3D form API (/frame3d), optimisation, the orchestrator tools and the
frontend (served via ``limits_payload()``), so chat / form / downloads always agree.

The solver is sparse (scipy.sparse assembly + SuperLU, ARPACK for the P-Δ critical load), so the limits
are set from benchmarks on the production VPS (2 vCPU, 4 GB RAM): the largest model must finish the full
analysis + Mabhas 9 design well within ~60 s and a few hundred MB of memory.
"""

from __future__ import annotations

MAX_STOREYS = 100
MAX_BAYS = 30  # per direction
MIN_SPAN_M = 1.5
MAX_SPAN_M = 15.0
MAX_NODES = 8000  # (bays_x+1)·(bays_y+1)·(storeys+1) — 30 storeys 15×15 ≈ 7 936 nodes ≈ 25-30 s, ~1.3 GB peak on the 2-vCPU VPS
# models above this many nodes run as a background job with progress in the chat UI
BACKGROUND_NODES = 1500
# member-size optimisation re-analyses the frame many times: smaller cap so a run fits its time budget
MAX_OPT_NODES = 1500
# response spectrum: all modes up to this count, else the leading modes reaching ≥ 90 % mass (at least this many)
MAX_RS_MODES = 30


def node_count(storeys: int, bays_x: int, bays_y: int) -> int:
    return (bays_x + 1) * (bays_y + 1) * (storeys + 1)


def element_count(storeys: int, bays_x: int, bays_y: int) -> int:
    per_level = (bays_x + 1) * (bays_y + 1) + bays_x * (bays_y + 1) + bays_y * (bays_x + 1)
    return storeys * per_level


def within_limits(storeys: int, bays_x: int, bays_y: int, *, optimisation: bool = False) -> bool:
    cap = MAX_OPT_NODES if optimisation else MAX_NODES
    return (1 <= storeys <= MAX_STOREYS and 1 <= bays_x <= MAX_BAYS and 1 <= bays_y <= MAX_BAYS
            and node_count(storeys, bays_x, bays_y) <= cap)


def limit_text(*, optimisation: bool = False) -> str:
    cap = MAX_OPT_NODES if optimisation else MAX_NODES
    return f"supports 1-{MAX_STOREYS} storeys, 1-{MAX_BAYS} bays per direction and at most {cap} nodes"


def limits_payload() -> dict[str, float | int]:
    return {"max_storeys": MAX_STOREYS, "max_bays": MAX_BAYS, "max_nodes": MAX_NODES,
            "max_opt_nodes": MAX_OPT_NODES, "min_span_m": MIN_SPAN_M, "max_span_m": MAX_SPAN_M,
            "background_nodes": BACKGROUND_NODES}
