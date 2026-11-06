"""Components, cut vertices, bridges and bipartiteness."""

from __future__ import annotations

from collections import deque
from collections.abc import Collection
from dataclasses import dataclass

from .graph import RoadGraph


def connected_components(graph: RoadGraph, removed: Collection[int] = ()) -> list[list[int]]:
    """Components, largest first. Vertices in `removed` are treated as deleted."""
    seen = [False] * graph.n
    for v in removed:
        seen[v] = True
    components = []
    for start in range(graph.n):
        if seen[start]:
            continue
        seen[start] = True
        component, stack = [start], [start]
        while stack:
            for w, _ in graph.adj[stack.pop()]:
                if not seen[w]:
                    seen[w] = True
                    component.append(w)
                    stack.append(w)
        components.append(component)
    return sorted(components, key=len, reverse=True)


@dataclass(frozen=True, slots=True)
class CutStructure:
    cut_vertices: set[int]  # Removing one disconnects its component.
    bridges: set[int]  # Road ids. Removing one disconnects its component.


def cut_structure(graph: RoadGraph) -> CutStructure:
    """Tarjan's low-link algorithm in one depth-first search, iterative to avoid stack limits.

    low[v] is the smallest discovery time reachable from v's subtree using one back edge.
    Tree edge (v, w) is a bridge iff low[w] > disc[v]. Non-root v is a cut vertex iff some child
    w has low[w] >= disc[v]. A root is a cut vertex iff it has two or more DFS children.
    """
    n = graph.n
    disc = [-1] * n
    low = [0] * n
    cut_vertices: set[int] = set()
    bridges: set[int] = set()
    clock = 0

    for root in range(n):
        if disc[root] != -1:
            continue
        disc[root] = low[root] = clock
        clock += 1
        root_children = 0
        stack: list[tuple[int, int, int]] = [(root, -1, 0)]  # vertex, road in, next neighbour
        while stack:
            v, road_in, i = stack.pop()
            if i < len(graph.adj[v]):
                stack.append((v, road_in, i + 1))
                w, road_id = graph.adj[v][i]
                if road_id == road_in:
                    continue
                if disc[w] == -1:
                    disc[w] = low[w] = clock
                    clock += 1
                    stack.append((w, road_id, 0))
                else:
                    low[v] = min(low[v], disc[w])
            elif stack:
                parent = stack[-1][0]
                low[parent] = min(low[parent], low[v])
                if low[v] > disc[parent]:
                    bridges.add(road_in)
                if parent == root:
                    root_children += 1
                elif low[v] >= disc[parent]:
                    cut_vertices.add(parent)
        if root_children >= 2:
            cut_vertices.add(root)
    return CutStructure(cut_vertices, bridges)


def two_colouring(graph: RoadGraph) -> tuple[bool, list[int]]:
    """Try to 2-colour the graph by BFS.

    A graph is bipartite iff it has no odd cycle. Returns (True, []) on success, otherwise
    (False, witness) where witness is an odd closed walk's vertex sequence (a proof of failure).
    """
    colour = [-1] * graph.n
    parent = [-1] * graph.n
    for start in range(graph.n):
        if colour[start] != -1:
            continue
        colour[start] = 0
        queue = deque([start])
        while queue:
            v = queue.popleft()
            for w, _ in graph.adj[v]:
                if colour[w] == -1:
                    colour[w] = 1 - colour[v]
                    parent[w] = v
                    queue.append(w)
                elif colour[w] == colour[v]:
                    return False, _odd_cycle(parent, v, w)
    return True, []


def _odd_cycle(parent: list[int], a: int, b: int) -> list[int]:
    """Join the two tree paths from a and b at their lowest common ancestor."""
    ancestors = {}
    x, steps = a, 0
    while x != -1:
        ancestors[x] = steps
        x, steps = parent[x], steps + 1
    path_b = []
    x = b
    while x not in ancestors:
        path_b.append(x)
        x = parent[x]
    path_a = []
    y = a
    while y != x:
        path_a.append(y)
        y = parent[y]
    return [x, *reversed(path_a), *path_b, x]
