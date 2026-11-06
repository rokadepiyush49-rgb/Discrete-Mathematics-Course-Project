import math
from itertools import combinations, product

import networkx as nx
import numpy as np
import pytest
from conftest import from_networkx
from hypothesis import given
from hypothesis import strategies as st

from route_resilience.combinatorics import (
    budget_generating_function,
    degree_generating_function,
    inclusion_exclusion,
    ladder_closed_form,
    ladder_spanning_trees,
    log10_spanning_trees,
    log10_spanning_trees_spectral,
    percolation_estimate,
    surjections,
)


@given(st.integers(0, 7), st.integers(1, 5))
def test_surjection_formula_matches_brute_force(jobs, crews):
    brute = sum(len(set(f)) == crews for f in product(range(crews), repeat=jobs))
    assert surjections(jobs, crews) == brute


@given(st.lists(st.sets(st.integers(0, 30), max_size=12), min_size=1, max_size=5))
def test_inclusion_exclusion_equals_direct_union(sets):
    named = dict(enumerate(sets))
    total, terms = inclusion_exclusion(named)
    assert total == len(set().union(*sets))
    assert len(terms) == 2 ** len(sets) - 1


def ladder(n):
    return nx.ladder_graph(n)


def test_ladder_recurrence_and_closed_form_match_matrix_tree():
    for n in range(2, 16):
        assert ladder_spanning_trees(n) == ladder_closed_form(n)
        laplacian = nx.laplacian_matrix(ladder(n)).toarray().astype(float)
        determinant = round(np.linalg.det(laplacian[1:, 1:]))
        assert determinant == ladder_spanning_trees(n)


def test_recurrence_relation_holds():
    for n in range(3, 25):
        t = ladder_spanning_trees
        assert t(n) == 4 * t(n - 1) - t(n - 2)


def test_matrix_tree_on_complete_graph_gives_cayley():
    for n in range(3, 9):
        expected = n ** (n - 2)  # Cayley's formula
        assert math.isclose(
            10 ** log10_spanning_trees(from_networkx(nx.complete_graph(n))), expected, rel_tol=1e-9
        )


def test_cofactor_and_eigenvalue_counts_agree():
    graph = from_networkx(nx.grid_2d_graph(12, 12))
    assert math.isclose(
        log10_spanning_trees(graph), log10_spanning_trees_spectral(graph), rel_tol=1e-9
    )


def test_disconnected_graph_is_rejected():
    with pytest.raises(ValueError):
        log10_spanning_trees(from_networkx(nx.disjoint_union(nx.path_graph(3), nx.path_graph(3))))


def test_degree_generating_function_is_a_distribution():
    p = degree_generating_function([1, 1, 2, 3])
    assert p == {1: 0.5, 2: 0.25, 3: 0.25}
    assert math.isclose(sum(p.values()), 1)  # G0(1) = 1


def test_percolation_on_a_regular_tree_like_graph():
    # Every vertex has degree 3, so each road leads to 2 more: G1'(1) = 2 and q_c = 1/2.
    estimate = percolation_estimate([3] * 100)
    assert estimate.branching_factor == 2
    assert estimate.critical_survival == 0.5


def test_no_giant_component_for_paths():
    assert percolation_estimate([1, 1]).critical_survival is None


@given(st.lists(st.integers(1, 6), max_size=9))
def test_budget_generating_function_counts_subsets(costs):
    coefficients = budget_generating_function(costs)
    assert sum(coefficients) == 2 ** len(costs)  # Setting x = 1 counts every subset
    for budget, count in enumerate(coefficients):
        brute = sum(
            sum(subset) == budget
            for r in range(len(costs) + 1)
            for subset in combinations(costs, r)
        )
        assert count == brute
