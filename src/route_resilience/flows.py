"""Edge-disjoint routes through unit-capacity maximum flow (Menger's theorem).

If k edge-disjoint routes join O and D, each closed road can break at most one of them. So by
the pigeonhole principle, k - 1 closures must leave one route open. Conversely, the max-flow
min-cut theorem finds a set of exactly k roads whose closure does cut O from D.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Collection
from dataclasses import dataclass

from .graph import RoadGraph


@dataclass(frozen=True, slots=True)
class DisjointRoutes:
    k: int
    routes: list[list[int]]  # Each route as a list of road ids from source to target
    min_cut: list[int]  # k road ids whose closure separates source from target


def edge_disjoint_routes(
    graph: RoadGraph, source: int, target: int, blocked: Collection[int] = ()
) -> DisjointRoutes:
    # flow[r] is the net flow on road r: +1 from u to v, -1 from v to u, 0 for none.
    flow = [0] * graph.m

    def residual(x: int, road_id: int) -> int:
        """Spare capacity for leaving x along this road, given capacity 1 each way."""
        road = graph.roads[road_id]
        return 1 - (flow[road_id] if x == road.u else -flow[road_id])

    def bfs() -> tuple[bool, dict[int, tuple[int, int]]]:
        parent: dict[int, tuple[int, int]] = {source: (-1, -1)}
        queue = deque([source])
        while queue:
            v = queue.popleft()
            for w, road_id in graph.adj[v]:
                if w not in parent and w not in blocked and residual(v, road_id) > 0:
                    parent[w] = (v, road_id)
                    if w == target:
                        return True, parent
                    queue.append(w)
        return False, parent

    k = 0
    while True:
        found, parent = bfs()
        if not found:
            break
        k += 1
        v = target
        while v != source:
            u, road_id = parent[v]
            flow[road_id] += 1 if u == graph.roads[road_id].u else -1
            v = u

    # `parent` now holds the source side of a minimum cut.
    source_side = parent
    min_cut = [
        road_id
        for road_id, road in enumerate(graph.roads)
        if (road.u in source_side) != (road.v in source_side)
        and road.u not in blocked
        and road.v not in blocked
    ]

    # Decompose the flow into k routes by walking it from the source.
    outgoing: dict[int, list[tuple[int, int]]] = {}
    for road_id, f in enumerate(flow):
        if f:
            road = graph.roads[road_id]
            a, b = (road.u, road.v) if f > 0 else (road.v, road.u)
            outgoing.setdefault(a, []).append((b, road_id))

    routes = []
    for _ in range(k):
        walk: list[tuple[int, int]] = []  # (vertex we arrived at, road taken)
        v = source
        while v != target:
            w, road_id = outgoing[v].pop()
            walk.append((w, road_id))
            v = w
        routes.append(_drop_loops(source, walk))
    return DisjointRoutes(k, routes, min_cut)


def _drop_loops(source: int, walk: list[tuple[int, int]]) -> list[int]:
    """A flow walk may revisit a vertex. Cutting the loop out leaves a simple path."""
    position = {source: 0}
    path: list[tuple[int, int]] = []
    for vertex, road_id in walk:
        if vertex in position:
            keep = position[vertex]
            for dropped, _ in path[keep:]:
                position.pop(dropped, None)
            path = path[:keep]
            position[vertex] = keep
        else:
            path.append((vertex, road_id))
            position[vertex] = len(path)
    return [road_id for _, road_id in path]
