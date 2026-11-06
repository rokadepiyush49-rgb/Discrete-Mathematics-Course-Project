"""Betweenness centrality by Brandes' algorithm: two recurrences on shortest-path DAGs.

Let σ(s, v) be the number of shortest s-v paths, and P(v) the predecessors of v on them.

  Path count:   σ(s, v) = Σ_{u ∈ P(v)} σ(s, u)                       with σ(s, s) = 1
  Dependency:   δ(s, v) = Σ_{w : v ∈ P(w)} σ(s, v)/σ(s, w) · (1 + δ(s, w))

Betweenness of v is Σ_s δ(s, v). Evaluating the first recurrence forwards and the second
backwards replaces a sum over all O(n²) pairs by one pass per source.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Iterable
from dataclasses import dataclass

from .graph import RoadGraph

EPS = 1e-9


@dataclass(frozen=True, slots=True)
class Betweenness:
    """Normalised scores in [0, 1], plus the raw pair-counts behind them."""

    nodes: list[float]
    roads: list[float]
    raw_nodes: list[float]


def brandes(
    graph: RoadGraph, sources: Iterable[int] | None = None, weights: list[float] | None = None
) -> Betweenness:
    n = graph.n
    weights = weights if weights is not None else graph.weights()
    adj = graph.adj
    chosen = list(range(n)) if sources is None else list(sources)

    node_score = [0.0] * n
    road_score = [0.0] * graph.m

    for s in chosen:
        dist = [math.inf] * n
        sigma = [0.0] * n
        preds: list[list[tuple[int, int]]] = [[] for _ in range(n)]
        settled = [False] * n
        order: list[int] = []
        dist[s] = 0.0
        sigma[s] = 1.0
        heap = [(0.0, s)]

        # Forward: Dijkstra, evaluating the path-count recurrence as vertices settle.
        while heap:
            d, v = heapq.heappop(heap)
            if settled[v]:
                continue
            settled[v] = True
            order.append(v)
            sigma_v = sigma[v]
            for w, road_id in adj[v]:
                if settled[w]:
                    continue
                nd = d + weights[road_id]
                if nd < dist[w] - EPS:
                    dist[w] = nd
                    sigma[w] = sigma_v
                    preds[w] = [(v, road_id)]
                    heapq.heappush(heap, (nd, w))
                elif nd <= dist[w] + EPS:
                    sigma[w] += sigma_v
                    preds[w].append((v, road_id))

        # Backward: evaluate the dependency recurrence, farthest vertices first.
        delta = [0.0] * n
        for w in reversed(order):
            coefficient = (1.0 + delta[w]) / sigma[w]
            for v, road_id in preds[w]:
                share = sigma[v] * coefficient
                delta[v] += share
                road_score[road_id] += share
            if w != s:
                node_score[w] += delta[w]

    # Undirected: every unordered pair was counted once from each end. If only some sources
    # were used, scale up to estimate the full sum.
    scale = 0.5 * (n / len(chosen))
    raw_nodes = [x * scale for x in node_score]
    node_pairs = (n - 1) * (n - 2) / 2
    road_pairs = n * (n - 1) / 2
    return Betweenness(
        nodes=[x / node_pairs for x in raw_nodes] if node_pairs else raw_nodes,
        roads=[x * scale / road_pairs for x in road_score],
        raw_nodes=raw_nodes,
    )
