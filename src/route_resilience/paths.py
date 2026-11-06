"""Shortest paths by Dijkstra's algorithm, written out in full."""

from __future__ import annotations

import heapq
import math
from collections.abc import Collection

from .graph import RoadGraph


def dijkstra(
    graph: RoadGraph,
    source: int,
    blocked: Collection[int] = (),
    weights: list[float] | None = None,
) -> tuple[list[float], list[int], list[int]]:
    """Return (distance, previous vertex, road used to arrive) for every vertex."""
    weights = weights if weights is not None else graph.weights()
    dist = [math.inf] * graph.n
    prev = [-1] * graph.n
    via = [-1] * graph.n
    dist[source] = 0.0
    heap = [(0.0, source)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist[v]:
            continue  # Stale heap entry: a shorter route was found after this was pushed.
        for w, road_id in graph.adj[v]:
            if w in blocked:
                continue
            nd = d + weights[road_id]
            if nd < dist[w]:
                dist[w] = nd
                prev[w] = v
                via[w] = road_id
                heapq.heappush(heap, (nd, w))
    return dist, prev, via


def shortest_path(
    graph: RoadGraph, source: int, target: int, blocked: Collection[int] = ()
) -> tuple[float, list[int], list[int]] | None:
    """Return (seconds, vertices, roads) for the fastest route, or None if unreachable."""
    if source in blocked or target in blocked:
        return None
    dist, prev, via = dijkstra(graph, source, blocked)
    if math.isinf(dist[target]):
        return None
    vertices, roads = [target], []
    while vertices[-1] != source:
        roads.append(via[vertices[-1]])
        vertices.append(prev[vertices[-1]])
    return dist[target], vertices[::-1], roads[::-1]
