"""Small dense modal-analysis helpers (pure Python, no numpy).

- ``jacobi_eigen``: symmetric eigen-decomposition (cyclic Jacobi).
- ``generalized_eigen_diag_mass``: K φ = ω² M φ for diagonal M.
- ``cqc_coefficient`` / ``combine_cqc`` / ``combine_srss``: modal combination.
"""

from __future__ import annotations

import math


def jacobi_eigen(a: list[list[float]], tol: float = 1e-12, max_sweeps: int = 100) -> tuple[list[float], list[list[float]]]:
    """Return (eigenvalues, eigenvectors as columns) of a symmetric matrix."""
    n = len(a)
    m = [list(map(float, row)) for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(max_sweeps):
        off = sum(m[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        scale = sum(m[i][i] ** 2 for i in range(n)) or 1.0
        if off <= tol * tol * scale:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(m[p][q]) < 1e-300:
                    continue
                theta = (m[q][q] - m[p][p]) / (2.0 * m[p][q])
                t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    mkp, mkq = m[k][p], m[k][q]
                    m[k][p] = c * mkp - s * mkq
                    m[k][q] = s * mkp + c * mkq
                for k in range(n):
                    mpk, mqk = m[p][k], m[q][k]
                    m[p][k] = c * mpk - s * mqk
                    m[q][k] = s * mpk + c * mqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    return [m[i][i] for i in range(n)], v


def generalized_eigen_diag_mass(k: list[list[float]], mass: list[float]) -> list[tuple[float, list[float]]]:
    """Solve K φ = ω² M φ (M diagonal, positive). Returns [(ω², φ)] sorted ascending, φᵀMφ = 1."""
    n = len(k)
    inv_sqrt = [1.0 / math.sqrt(mi) for mi in mass]
    a = [[k[i][j] * inv_sqrt[i] * inv_sqrt[j] for j in range(n)] for i in range(n)]
    for i in range(n):  # enforce symmetry
        for j in range(i + 1, n):
            avg = 0.5 * (a[i][j] + a[j][i]); a[i][j] = a[j][i] = avg
    vals, vecs = jacobi_eigen(a)
    out = []
    for idx in range(n):
        phi = [vecs[i][idx] * inv_sqrt[i] for i in range(n)]
        out.append((vals[idx], phi))
    out.sort(key=lambda item: item[0])
    return out


def cqc_coefficient(wi: float, wj: float, zeta: float = 0.05) -> float:
    r = wj / wi
    return (8 * zeta * zeta * (1 + r) * r ** 1.5) / ((1 - r * r) ** 2 + 4 * zeta * zeta * r * (1 + r) ** 2)


def combine_cqc(values: list[float], omegas: list[float], zeta: float = 0.05) -> float:
    total = 0.0
    for i, vi in enumerate(values):
        if vi == 0.0:
            continue
        for j, vj in enumerate(values):
            if vj == 0.0:
                continue
            total += (1.0 if i == j else cqc_coefficient(omegas[i], omegas[j], zeta)) * vi * vj
    return math.sqrt(max(total, 0.0))


def combine_srss(values: list[float]) -> float:
    return math.sqrt(sum(v * v for v in values))
