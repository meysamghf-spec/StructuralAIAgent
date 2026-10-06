"""Unit tests for the in-repo 3D space-frame solver."""

from __future__ import annotations

from app.application.analysis.frame3d_solver import (
    SpaceElement,
    SpaceFrameModel,
    SpaceFrameSolverError,
    SpaceNodalLoad,
    SpaceNode,
    SpaceSupport,
    solve_space_frame,
    torsion_constant_rectangle,
)
from app.application.analysis.linear_algebra import factor_linear_system, solve_linear_system


def test_lu_matches_dense_solve() -> None:
    matrix = [[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]]
    rhs = [1.0, 2.0, 3.0]
    dense = solve_linear_system(matrix, rhs)
    factored = factor_linear_system(matrix).solve(rhs)
    assert all(abs(a - b) < 1e-10 for a, b in zip(dense, factored, strict=True))


def test_cantilever_tip_load_matches_beam_theory() -> None:
    length = 5.0
    elastic = 30_000_000.0
    width, depth = 0.3, 0.5
    iy = width * depth**3 / 12.0
    iz = depth * width**3 / 12.0
    area = width * depth
    load = -10.0
    model = SpaceFrameModel(
        id="cantilever",
        nodes=[
            SpaceNode(id="N1", x=0.0, y=0.0, z=0.0),
            SpaceNode(id="N2", x=length, y=0.0, z=0.0),
        ],
        elements=[
            SpaceElement(
                id="E1",
                start_node_id="N1",
                end_node_id="N2",
                elastic_modulus=elastic,
                area=area,
                iy=iy,
                iz=iz,
                j=torsion_constant_rectangle(width, depth),
            )
        ],
        supports=[SpaceSupport(node_id="N1")],
        nodal_loads=[SpaceNodalLoad(node_id="N2", fz=load)],
    )
    result = solve_space_frame(model)
    assert result.status == "SUCCESS"
    expected = load * length**3 / (3.0 * elastic * iy)
    assert abs(result.displacements["N2"][2] - expected) / abs(expected) < 0.02
    assert abs(result.displacements["N2"][0]) < 1e-8
    assert abs(result.displacements["N2"][1]) < 1e-8


def test_column_axial_shortening() -> None:
    length = 3.0
    elastic = 25_000_000.0
    area = 0.16
    load = -400.0
    model = SpaceFrameModel(
        id="column",
        nodes=[
            SpaceNode(id="BASE", x=0.0, y=0.0, z=0.0),
            SpaceNode(id="TOP", x=0.0, y=0.0, z=length),
        ],
        elements=[
            SpaceElement(
                id="COL",
                start_node_id="BASE",
                end_node_id="TOP",
                elastic_modulus=elastic,
                area=area,
                iy=0.002,
                iz=0.002,
                j=0.003,
            )
        ],
        supports=[SpaceSupport(node_id="BASE")],
        nodal_loads=[SpaceNodalLoad(node_id="TOP", fz=load)],
    )
    result = solve_space_frame(model)
    expected = load * length / (elastic * area)
    assert abs(result.displacements["TOP"][2] - expected) / abs(expected) < 0.02
    assert result.member_forces["COL"].max_abs_axial > 0


def test_unsupported_frame_is_singular() -> None:
    model = SpaceFrameModel(
        id="free",
        nodes=[
            SpaceNode(id="N1", x=0.0, y=0.0, z=0.0),
            SpaceNode(id="N2", x=3.0, y=0.0, z=0.0),
        ],
        elements=[
            SpaceElement(
                id="E1",
                start_node_id="N1",
                end_node_id="N2",
                elastic_modulus=2.5e7,
                area=0.1,
                iy=0.001,
                iz=0.001,
                j=0.002,
            )
        ],
        supports=[],
        nodal_loads=[SpaceNodalLoad(node_id="N2", fz=-1.0)],
    )
    try:
        solve_space_frame(model)
        raise AssertionError("expected solver error")
    except SpaceFrameSolverError as exc:
        assert exc.status in {"UNSTABLE", "SINGULAR", "FAILED"}
