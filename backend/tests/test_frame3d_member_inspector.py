from app.application.frame3d_chat_analysis import build_frame3d_payload
from tests.test_frame3d_chat_analysis import PROMPT


def test_viewer_has_full_end_forces_and_material():
    p = build_frame3d_payload(PROMPT)
    v = p.get("viewer") or (p.get("results") or {}).get("viewer")
    assert v, list(p)
    f6 = v["forces6"]
    case = next(iter(f6))
    row = next(iter(f6[case].values()))
    assert len(row) == 12
    # axial at i equals the compact row's N
    mid, compact = next(iter(v["forces"][case].items()))
    assert abs(f6[case][mid][0] - compact[0]) < 1e-6
    assert v["material"]["fc_mpa"] > 0
