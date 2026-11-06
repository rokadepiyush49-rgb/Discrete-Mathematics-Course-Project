"""Post-disaster road inspection as the Route Inspection (Chinese Postman) problem.

A vehicle must drive every road in a sector and return to base. A closed walk using each edge
exactly once is an Euler tour, which exists iff every degree is even. So we pair up the
odd-degree vertices (always an even number, by the handshake lemma), duplicate the shortest
paths between pairs, and read off the tour with Hierholzer's algorithm.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

import networkx as nx

from .graph import Road, RoadGraph
from .paths import dijkstra


@dataclass(frozen=True, slots=True)
class InspectionTour:
    start: int
    vertices: list[int]  # In the original graph's numbering
    roads: list[int]  # Road ids in travel order. Repeats are the deadheading.
    sector_roads: int
    odd_vertices: int
    road_length_m: float
    deadhead_m: float


def hierholzer(edges: list[tuple[int, int]], start: int) -> list[tuple[int, int]]:
    """Euler tour of a connected multigraph with all even degrees.

    Returns (vertex, edge index) steps, where the first step's edge index is -1.
    """
    adjacency: dict[int, list[tuple[int, int]]] = {}
    for index, (u, v) in enumerate(edges):
        adjacency.setdefault(u, []).append((v, index))
        adjacency.setdefault(v, []).append((u, index))
    used = [False] * len(edges)
    stack: list[tuple[int, int]] = [(start, -1)]
    tour: list[tuple[int, int]] = []
    while stack:
        v, arrived_by = stack[-1]
        options = adjacency[v]
        while options and used[options[-1][1]]:
            options.pop()
        if options:
            w, index = options.pop()
            used[index] = True
            stack.append((w, index))
        else:
            tour.append((v, arrived_by))
            stack.pop()
    # The stack unwinds backwards, so the tour comes out reversed. Each step's edge joins it to
    # the step before: a popped vertex's parent is either popped next, or is returned to by
    # an excursion that must close there because every degree is even.
    tour.reverse()
    return tour


def inspection_tour(
    graph: RoadGraph, centre: int, radius_s: float, blocked: Collection[int] = ()
) -> InspectionTour:
    distance, _, _ = dijkstra(graph, centre, blocked)
    # A shortest path stays within its endpoint's radius, so this sector is connected.
    sector = [v for v in range(graph.n) if distance[v] <= radius_s]
    index = {v: i for i, v in enumerate(sector)}
    road_ids = [
        road_id for road_id, road in enumerate(graph.roads) if road.u in index and road.v in index
    ]
    sub = RoadGraph(graph.coords[v] for v in sector)
    for road_id in road_ids:
        road = graph.roads[road_id]
        sub.add_road(Road(index[road.u], index[road.v], road.length, road.time))

    odd = [v for v in range(sub.n) if sub.degree(v) % 2]
    edges = [(r.u, r.v) for r in sub.roads]
    edge_road = list(road_ids)
    deadhead = 0.0

    if odd:
        lengths = sub.weights("length")
        trees = {v: dijkstra(sub, v, weights=lengths) for v in odd}
        pairing = nx.Graph()
        for i, a in enumerate(odd):
            for b in odd[i + 1 :]:
                pairing.add_edge(a, b, weight=trees[a][0][b])
        for a, b in nx.min_weight_matching(pairing):
            deadhead += trees[a][0][b]
            _, prev, via = trees[a]
            v = b
            while v != a:  # Duplicate each road on the shortest a-b path.
                edges.append((prev[v], v))
                edge_road.append(road_ids[via[v]])
                v = prev[v]

    steps = hierholzer(edges, index[centre])
    return InspectionTour(
        start=centre,
        vertices=[sector[v] for v, _ in steps],
        roads=[edge_road[e] for _, e in steps[1:]],
        sector_roads=len(road_ids),
        odd_vertices=len(odd),
        road_length_m=sum(graph.roads[r].length for r in road_ids),
        deadhead_m=deadhead,
    )
