"""Counting tools (syllabus Units 2, 3 and 4), each tied to a question about the network."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.linalg import lu_factor

from .graph import RoadGraph


def failure_scenarios(n: int, k: int) -> int:
    """C(n, k): how many ways k junctions can fail at once."""
    return math.comb(n, k)


def surjections(jobs: int, crews: int) -> int:
    """Onto functions from jobs to crews, by inclusion-exclusion.

    Counts the job assignments that leave no crew idle:
    Σ (-1)^i C(k, i) (k - i)^m.
    """
    return sum((-1) ** i * math.comb(crews, i) * (crews - i) ** jobs for i in range(crews + 1))


@dataclass(frozen=True, slots=True)
class InclusionExclusionTerm:
    subset: tuple
    size: int
    sign: int


def inclusion_exclusion[T: Hashable](
    sets: dict[T, set],
) -> tuple[int, list[InclusionExclusionTerm]]:
    """|A1 ∪ ... ∪ Ak| as the alternating sum over all non-empty sub-collections."""
    keys = list(sets)
    total = 0
    terms = []
    for r in range(1, len(keys) + 1):
        sign = 1 if r % 2 else -1
        for subset in combinations(keys, r):
            common = set.intersection(*(sets[k] for k in subset))
            total += sign * len(common)
            terms.append(InclusionExclusionTerm(subset, len(common), sign))
    return total, terms


# --- Recurrences ---------------------------------------------------------------------------


def ladder_spanning_trees(n: int) -> int:
    """Spanning trees of an n-rung ladder: two parallel roads joined by n cross streets.

    Satisfies the linear homogeneous recurrence t(n) = 4 t(n-1) - t(n-2), t(1) = 1, t(2) = 4.
    """
    if n == 1:
        return 1
    previous, current = 1, 4
    for _ in range(n - 2):
        previous, current = current, 4 * current - previous
    return current


def ladder_closed_form(n: int) -> int:
    """Solve the recurrence: the characteristic equation x² - 4x + 1 = 0 has roots 2 ± √3.

    Fitting t(1) and t(2) gives t(n) = ((2 + √3)^n - (2 - √3)^n) / (2√3).
    """
    root = math.sqrt(3)
    return round(((2 + root) ** n - (2 - root) ** n) / (2 * root))


def _laplacian(graph: RoadGraph) -> np.ndarray:
    laplacian = -graph.adjacency_matrix().toarray().astype(np.float64)
    np.fill_diagonal(laplacian, -laplacian.sum(axis=1))
    return laplacian


def log10_spanning_trees(graph: RoadGraph) -> float:
    """log10 of the spanning tree count, by Kirchhoff's Matrix-Tree Theorem.

    The count equals any cofactor of the Laplacian L = D - A. It is astronomically large for a
    city, so we sum logarithms of the pivots rather than form the determinant itself.
    Requires a connected graph.
    """
    pivots = np.abs(np.diag(lu_factor(_laplacian(graph)[1:, 1:], check_finite=False)[0]))
    if pivots.min() < 1e-9:
        raise ValueError("graph is not connected")
    return float(np.log10(pivots).sum())


def log10_spanning_trees_spectral(graph: RoadGraph) -> float:
    """The same count from the eigenvalues: τ(G) = (1/n) Π λ_i over the non-zero λ_i."""
    eigenvalues = np.linalg.eigvalsh(_laplacian(graph))
    return float(np.log10(eigenvalues[1:]).sum() - math.log10(graph.n))


# --- Generating functions ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PercolationEstimate:
    """What the degree generating function predicts about random failure."""

    mean_degree: float
    branching_factor: float  # G1'(1): expected onward roads from a road's far end
    critical_survival: float | None  # Smallest surviving fraction that keeps a giant component


def degree_generating_function(degrees: Iterable[int]) -> dict[int, float]:
    """G0(x) = Σ p_k x^k, returned as its coefficients {k: p_k}."""
    counts = Counter(degrees)
    total = sum(counts.values())
    return {k: c / total for k, c in sorted(counts.items())}


def percolation_estimate(degrees: Iterable[int]) -> PercolationEstimate:
    """Molloy-Reed threshold from G0.

    G1(x) = G0'(x) / G0'(1) generates the excess degree: the roads leaving a junction reached by
    following a random road. A giant component needs G1'(1) > 1, and when a fraction q of
    vertices survive it persists while q * G1'(1) > 1, so the critical q is 1 / G1'(1).
    """
    p = degree_generating_function(degrees)
    g0_prime_1 = sum(k * pk for k, pk in p.items())  # = mean degree
    g0_second_1 = sum(k * (k - 1) * pk for k, pk in p.items())
    branching = g0_second_1 / g0_prime_1  # G1'(1)
    critical = 1 / branching if branching > 1 else None
    return PercolationEstimate(g0_prime_1, branching, critical)


def budget_generating_function(costs: Sequence[int]) -> list[int]:
    """Coefficients of Π (1 + x^c): entry b counts the subsets of jobs costing exactly b."""
    coefficients = [1]
    for cost in costs:
        grown = coefficients + [0] * cost
        for i, value in enumerate(coefficients):
            grown[i + cost] += value
        coefficients = grown
    return coefficients
