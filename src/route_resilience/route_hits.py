"""Which trips does a closure hit? Input for inclusion-exclusion on overlapping failures."""

from __future__ import annotations

from collections.abc import Sequence

from scipy.sparse.csgraph import dijkstra as scipy_dijkstra

from .graph import RoadGraph


def route_hit_sets(
    graph: RoadGraph, closures: Sequence[int], sources: Sequence[int]
) -> dict[int, set[tuple[int, int]]]:
    """For each closure v, the trips (s, t) whose fastest route passes through v.

    In the shortest-path tree of s, those trips are exactly the proper descendants of v.
    """
    _, predecessors = scipy_dijkstra(
        graph.weight_matrix(), directed=False, indices=list(sources), return_predecessors=True
    )
    hits: dict[int, set[tuple[int, int]]] = {v: set() for v in closures}
    for row, s in enumerate(sources):
        children: dict[int, list[int]] = {}
        for t, parent in enumerate(predecessors[row].tolist()):
            if parent >= 0:
                children.setdefault(parent, []).append(t)
        for v in closures:
            if v == s:
                continue
            stack = list(children.get(v, ()))
            while stack:
                t = stack.pop()
                hits[v].add((s, t))
                stack.extend(children.get(t, ()))
    return hits
