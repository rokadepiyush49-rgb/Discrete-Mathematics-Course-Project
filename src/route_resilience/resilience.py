"""Stress testing: remove junctions and measure what the network loses."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import asdict, dataclass

import numpy as np
from scipy.sparse.csgraph import dijkstra as scipy_dijkstra

from .centrality import brandes
from .connectivity import connected_components
from .dsu import DisjointSet
from .graph import RoadGraph
from .number_theory import AffinePermutation


@dataclass(frozen=True, slots=True)
class NetworkState:
    average_path_s: float  # Mean travel time over pairs that can still reach each other
    efficiency: float  # Mean of 1/d over all pairs, with 1/∞ = 0
    reachable_pairs: float  # Fraction of pairs still connected
    largest_component: float  # Fraction of surviving vertices in the largest component


def sample_sources(graph: RoadGraph, count: int, seed: int = 11) -> list[int]:
    """Distinct source vertices taken from an affine permutation of the vertex set."""
    permutation = AffinePermutation.from_seed(graph.n, seed)
    return [permutation(i) for i in range(min(count, graph.n))]


def evaluate(
    graph: RoadGraph, removed: Collection[int] = (), sources: Sequence[int] | None = None
) -> NetworkState:
    """Measure the network with `removed` deleted, using every source unless told otherwise."""
    dead = set(removed)
    alive = np.ones(graph.n, dtype=bool)
    alive[list(dead)] = False
    chosen = np.array(
        [s for s in (sources if sources is not None else range(graph.n)) if s not in dead]
    )

    distances = scipy_dijkstra(graph.weight_matrix(dead), directed=False, indices=chosen)
    distances = distances[:, alive]

    # Mask each source's distance to itself.
    columns = np.cumsum(alive) - 1
    mask = np.ones(distances.shape, dtype=bool)
    mask[np.arange(len(chosen)), columns[chosen]] = False

    values = distances[mask]
    finite = np.isfinite(values)
    with np.errstate(divide="ignore"):
        reciprocal = np.where(finite, 1.0 / values, 0.0)

    components = connected_components(graph, dead)
    return NetworkState(
        average_path_s=float(values[finite].mean()) if finite.any() else float("inf"),
        efficiency=float(reciprocal.mean()),
        reachable_pairs=float(finite.mean()),
        largest_component=len(components[0]) / int(alive.sum()) if components else 0.0,
    )


def resilience_index(base: NetworkState, after: NetworkState) -> dict[str, float]:
    """Two indices. 1 means unharmed, and lower means worse.

    `average_path` is the problem statement's ratio of average shortest path lengths. It only
    sees pairs that can still connect, so it can *rise* when a failure strands long trips.
    `efficiency` counts a stranded pair as a total loss, which stays well defined.
    """
    return {
        "average_path": base.average_path_s / after.average_path_s,
        "efficiency": after.efficiency / base.efficiency,
    }


def stress_curve(
    graph: RoadGraph, order: Sequence[int], steps: int, sources: Sequence[int] | None = None
) -> list[dict]:
    """Remove vertices one by one in the given order, recording the state after each."""
    base = evaluate(graph, (), sources)
    curve = [{"removed": 0, **asdict(base), **_index(base, base)}]
    for k in range(1, steps + 1):
        state = evaluate(graph, order[:k], sources)
        curve.append({"removed": k, **asdict(state), **_index(base, state)})
    return curve


def _index(base: NetworkState, state: NetworkState) -> dict[str, float]:
    index = resilience_index(base, state)
    return {"r_average_path": index["average_path"], "r_efficiency": index["efficiency"]}


def adaptive_order(graph: RoadGraph, steps: int, sample: int = 48) -> list[int]:
    """Attack order that recomputes betweenness after every removal, on a sample of sources.

    Each removal reroutes traffic, so the next most critical junction can change.
    """
    working = graph.copy()
    removed: list[int] = []
    weights = working.weights()
    infinite = 1e12  # Effectively deletes a road from every shortest path.
    for _ in range(steps):
        sources = [s for s in sample_sources(working, sample + len(removed)) if s not in removed]
        scores = brandes(working, sources[:sample], weights).nodes
        for r in removed:
            scores[r] = -1.0
        target = max(range(working.n), key=scores.__getitem__)
        removed.append(target)
        for _, road_id in working.adj[target]:
            weights[road_id] = infinite
    return removed


def percolation_curve(graph: RoadGraph, runs: int = 40, seed: int = 3) -> dict:
    """Largest component against surviving fraction, by the Newman-Ziff method.

    Junctions are switched back on in random order while a Disjoint Set tracks the largest
    component, so a whole curve costs one near-linear pass instead of n separate searches.
    """
    n = graph.n
    rng = np.random.default_rng(seed)
    totals = np.zeros(n + 1)
    for _ in range(runs):
        dsu = DisjointSet(n)
        active = [False] * n
        largest = 0
        for i, v in enumerate(rng.permutation(n).tolist(), start=1):
            active[v] = True
            largest = max(largest, 1)
            for w, _ in graph.adj[v]:
                if active[w]:
                    dsu.union(v, w)
                    largest = max(largest, dsu.size[dsu.find(v)])
            totals[i] += largest
    curve = totals / (runs * n)
    survival = np.arange(n + 1) / n

    # The transition is where the giant component grows fastest.
    window = max(5, n // 100)
    smooth = np.convolve(curve, np.ones(window) / window, mode="same")
    critical = float(survival[int(np.argmax(np.gradient(smooth[window:-window]))) + window])
    samples = sorted({*range(0, n, max(1, n // 100)), n})  # Keep the full network as an end point
    return {
        "survival": [round(float(survival[i]), 4) for i in samples],
        "largest_component": [round(float(curve[i]), 4) for i in samples],
        "critical_survival": critical,
    }
