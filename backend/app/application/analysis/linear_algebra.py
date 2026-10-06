"""
Dense linear solver used by the structural analysis engine.

Pure Python on purpose: the backend has no numpy/scipy dependency and the frame
models generated for a preliminary building design are small (a few hundred
degrees of freedom), which Gaussian elimination with partial pivoting handles in
well under a second.
"""

from __future__ import annotations


class SingularMatrixError(Exception):
    """Raised when the stiffness matrix has no unique solution."""

    def __init__(self, pivot_row: int) -> None:
        self.pivot_row = pivot_row
        super().__init__(
            f"Stiffness matrix is singular at degree of freedom {pivot_row}. "
            "The structure is unstable or insufficiently restrained."
        )


def solve_linear_system(
    matrix: list[list[float]],
    rhs: list[float],
    *,
    pivot_tolerance: float = 1e-12,
) -> list[float]:
    """
    Solve ``matrix @ x = rhs`` by Gaussian elimination with partial pivoting.

    ``matrix`` is copied, so the caller's stiffness matrix is left intact.
    """
    size = len(rhs)
    if size == 0:
        return []
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise ValueError("Coefficient matrix must be square and match the right-hand side length")

    augmented = [list(row) + [rhs[index]] for index, row in enumerate(matrix)]
    scale = max(
        (abs(value) for row in augmented for value in row[:size]),
        default=0.0,
    )
    threshold = pivot_tolerance * max(scale, 1.0)

    for column in range(size):
        pivot_row = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot_row][column]) <= threshold:
            raise SingularMatrixError(column)
        if pivot_row != column:
            augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]

        pivot = augmented[column][column]
        pivot_values = augmented[column]
        for row in range(column + 1, size):
            factor = augmented[row][column] / pivot
            if factor == 0.0:
                continue
            target = augmented[row]
            for index in range(column, size + 1):
                target[index] -= factor * pivot_values[index]

    solution = [0.0] * size
    for row in range(size - 1, -1, -1):
        total = augmented[row][size]
        row_values = augmented[row]
        for column in range(row + 1, size):
            total -= row_values[column] * solution[column]
        solution[row] = total / row_values[row]
    return solution


class LUFactorization:
    """Cached LU factorization so multiple load vectors reuse one stiffness matrix."""

    def __init__(self, lu: list[list[float]], origin_rows: list[int], threshold: float) -> None:
        self.lu = lu
        self.origin_rows = origin_rows
        self.threshold = threshold
        self.size = len(origin_rows)

    def solve(self, rhs: list[float]) -> list[float]:
        if len(rhs) != self.size:
            raise ValueError("Right-hand side length does not match the factored matrix")
        size = self.size
        pb = [rhs[index] for index in self.origin_rows]
        y = [0.0] * size
        for row in range(size):
            total = pb[row]
            row_values = self.lu[row]
            for column in range(row):
                total -= row_values[column] * y[column]
            y[row] = total
        x = [0.0] * size
        for row in range(size - 1, -1, -1):
            total = y[row]
            row_values = self.lu[row]
            for column in range(row + 1, size):
                total -= row_values[column] * x[column]
            if abs(row_values[row]) <= self.threshold:
                raise SingularMatrixError(row)
            x[row] = total / row_values[row]
        return x


def factor_linear_system(
    matrix: list[list[float]],
    *,
    pivot_tolerance: float = 1e-12,
) -> LUFactorization:
    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("Coefficient matrix must be square")
    lu = [list(row) for row in matrix]
    origin_rows = list(range(size))
    scale = max((abs(value) for row in lu for value in row), default=0.0)
    threshold = pivot_tolerance * max(scale, 1.0)
    for column in range(size):
        pivot_row = max(range(column, size), key=lambda row: abs(lu[row][column]))
        if abs(lu[pivot_row][column]) <= threshold:
            raise SingularMatrixError(column)
        if pivot_row != column:
            lu[column], lu[pivot_row] = lu[pivot_row], lu[column]
            origin_rows[column], origin_rows[pivot_row] = origin_rows[pivot_row], origin_rows[column]
        pivot = lu[column][column]
        for row in range(column + 1, size):
            factor = lu[row][column] / pivot
            lu[row][column] = factor
            for index in range(column + 1, size):
                lu[row][index] -= factor * lu[column][index]
    return LUFactorization(lu, origin_rows, threshold)
