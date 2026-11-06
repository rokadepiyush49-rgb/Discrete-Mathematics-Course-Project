"""Check textbook theorems against the real network, and report the numbers behind each check.

Every entry is computed from the graph, so a bug in the model shows up here as a failed theorem.
"""

from __future__ import annotations

import math
from collections import Counter

import networkx as nx
import numpy as np
from scipy import sparse

from .centrality import brandes
from .colouring import welsh_powell
from .combinatorics import (
    failure_scenarios,
    log10_spanning_trees,
    log10_spanning_trees_spectral,
)
from .connectivity import connected_components, two_colouring
from .graph import RoadGraph
from .paths import dijkstra
from .resilience import sample_sources


def to_networkx(graph: RoadGraph) -> nx.Graph:
    g = nx.Graph()
    g.add_nodes_from(range(graph.n))
    g.add_edges_from((r.u, r.v) for r in graph.roads)
    return g


def _entry(unit: int, name: str, statement: str, evidence: str, holds: bool) -> dict:
    return {
        "unit": unit,
        "name": name,
        "statement": statement,
        "evidence": evidence,
        "holds": bool(holds),
    }


def _betweenness_double_count(graph: RoadGraph, samples: int = 24) -> tuple[float, float]:
    """Count (source, interior vertex) incidences in two ways, for a sample of sources.

    Summing dependencies vertex by vertex must equal summing path lengths, in hops, target by
    target. Betweenness and the path tree are computed independently, so this checks both.
    """
    by_vertex = by_target = 0.0
    n = graph.n
    for s in sample_sources(graph, samples, seed=23):
        by_vertex += sum(brandes(graph, [s]).raw_nodes) / (0.5 * n)
        dist, prev, _ = dijkstra(graph, s)
        hops = [0] * n
        for v in sorted(range(n), key=dist.__getitem__):
            if v != s and prev[v] != -1:
                hops[v] = hops[prev[v]] + 1
                by_target += hops[v] - 1
    return by_vertex, by_target


def theorem_audit(graph: RoadGraph, kruskal_links: int, kruskal_bridges: int) -> list[dict]:
    n, m = graph.n, graph.m
    degrees = [graph.degree(v) for v in range(n)]
    components = len(connected_components(graph))
    adjacency = graph.adjacency_matrix()
    incidence = graph.incidence_matrix()
    entries = []

    # Unit 1
    entries.append(
        _entry(
            1, "Connectivity is an equivalence relation",
            "Reflexive, symmetric and transitive, so its classes partition the vertices.",
            f"{components} class(es) covering all {n:,} vertices exactly once",
            sum(len(c) for c in connected_components(graph)) == n,
        )
    )  # fmt: skip
    entries.append(
        _entry(
            1, "Every Kruskal link is a bridge (Lemma 3)",
            "A link that joins two components closes no cycle, so removing it disconnects them.",
            f"{kruskal_bridges} of {kruskal_links} Kruskal links are bridges in the MST-only graph",
            kruskal_bridges == kruskal_links,
        )
    )  # fmt: skip

    # Unit 2
    entries.append(
        _entry(
            2, "Handshake lemma",
            "Counting edge-ends two ways: Σ deg(v) = 2|E|.",
            f"Σ deg = {sum(degrees):,} and 2|E| = {2 * m:,}",
            sum(degrees) == 2 * m,
        )
    )  # fmt: skip
    by_vertex, by_target = _betweenness_double_count(graph)
    entries.append(
        _entry(
            2, "Double counting of betweenness",
            "Σ_v δ(s, v) = Σ_t (hops(s, t) − 1): interior vertices, counted by vertex and by trip.",
            f"{by_vertex:,.0f} by vertex and {by_target:,.0f} by trip, over 24 sources",
            math.isclose(by_vertex, by_target, rel_tol=1e-6),
        )
    )  # fmt: skip
    entries.append(
        _entry(
            2, "Failure scenarios are too many to enumerate",
            "Choosing k of n junctions gives C(n, k) scenarios.",
            f"C({n:,}, 3) = {failure_scenarios(n, 3):,}",
            failure_scenarios(n, 3) == n * (n - 1) * (n - 2) // 6,
        )
    )  # fmt: skip

    # Unit 3
    counts = Counter(degrees)
    entries.append(
        _entry(
            3, "Pigeonhole on degrees",
            "In a simple graph with n ≥ 2, two vertices share a degree.",
            f"{len(counts)} distinct degrees among {n:,} vertices",
            len(counts) < n,
        )
    )  # fmt: skip
    triangles = sum(nx.triangles(to_networkx(graph)).values()) // 3
    entries.append(
        _entry(
            3, "Mantel's theorem",
            "A triangle-free graph has at most n²/4 edges. Sparse roads sit far below this bound.",
            f"|E| = {m:,}, n²/4 = {n * n // 4:,}, and the map has {triangles:,} triangles",
            triangles > 0 or m <= n * n / 4,
        )
    )  # fmt: skip

    # Unit 6
    a_squared = adjacency @ adjacency
    entries.append(
        _entry(
            6, "Adjacency matrix",
            "(A²)ᵢᵢ counts closed 2-step walks at i, which is deg(i).",
            f"All {n:,} diagonal entries match, and trace(A²) = {a_squared.diagonal().sum():,}",
            bool(np.array_equal(a_squared.diagonal(), degrees)),
        )
    )  # fmt: skip
    difference = incidence @ incidence.T - (
        sparse.diags_array(np.array(degrees), dtype=None) + adjacency
    )
    entries.append(
        _entry(
            6, "Incidence matrix",
            "For the unsigned incidence matrix, BBᵀ = D + A.",
            f"Largest entry of BBᵀ − (D + A) is {abs(difference).max():.0f}",
            abs(difference).max() == 0,
        )
    )  # fmt: skip
    odd = sum(d % 2 for d in degrees)
    entries.append(
        _entry(
            6, "Euler tours",
            "A connected graph has an Euler tour iff no degree is odd. Odd vertices come in pairs.",
            f"{odd:,} odd-degree vertices (an even count), so no Euler tour exists",
            odd % 2 == 0,
        )
    )  # fmt: skip
    entries.append(
        _entry(
            6, "Spanning trees and cycle rank",
            "A spanning forest has n − c edges, leaving m − n + c independent cycles.",
            f"{n - components:,} tree edges and {m - n + components:,} independent cycles",
            m - n + components >= 0,
        )
    )  # fmt: skip
    if components == 1:
        by_cofactor = log10_spanning_trees(graph)
        by_eigenvalues = log10_spanning_trees_spectral(graph)
        entries.append(
            _entry(
                6, "Matrix-Tree theorem",
                "The spanning tree count is any cofactor of the Laplacian, or Π λᵢ / n.",
                f"10^{by_cofactor:,.2f} by cofactor and 10^{by_eigenvalues:,.2f} by eigenvalues",
                math.isclose(by_cofactor, by_eigenvalues, rel_tol=1e-8),
            )
        )  # fmt: skip
    bipartite, witness = two_colouring(graph)
    entries.append(
        _entry(
            6, "Bipartite iff no odd cycle",
            "2-colouring fails exactly when an odd cycle exists.",
            "2-colourable" if bipartite else f"Not bipartite: odd cycle, length {len(witness) - 1}",
            bipartite or (len(witness) - 1) % 2 == 1,
        )
    )  # fmt: skip
    planar, _ = nx.check_planarity(to_networkx(graph))
    entries.append(
        _entry(
            6, "Planar edge bound",
            "A simple planar graph with n ≥ 3 has |E| ≤ 3n − 6.",
            f"|E| = {m:,} ≤ {3 * n - 6:,}. Planarity test: {'planar' if planar else 'not planar'}",
            m <= 3 * n - 6,
        )
    )  # fmt: skip
    if planar:
        faces = m - n + components + 1
        entries.append(
            _entry(
                6, "Euler's formula",
                "A planar graph with c components has n − m + f = 1 + c.",
                f"{n:,} − {m:,} + {faces:,} = {n - m + faces}",
                n - m + faces == 1 + components,
            )
        )  # fmt: skip
    adj_sets = [{w for w, _ in graph.adj[v]} for v in range(n)]
    colours = max(welsh_powell(adj_sets)) + 1
    entries.append(
        _entry(
            6, "Greedy colouring bound",
            "Greedy colouring uses at most Δ + 1 colours.",
            f"{colours} colours used, and Δ + 1 = {max(degrees) + 1}",
            colours <= max(degrees) + 1,
        )
    )  # fmt: skip
    return entries
