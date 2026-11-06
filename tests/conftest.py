"""Shared helpers. NetworkX is the independent oracle for the hand-written algorithms."""

from __future__ import annotations

import networkx as nx
import pytest

from route_resilience.graph import Road, RoadGraph
from route_resilience.pipeline import SNAPSHOT, build_scene


def from_networkx(g: nx.Graph, weight: float | None = None) -> RoadGraph:
    """Build a RoadGraph on nodes 0..n-1. Edge weight comes from `w`, or defaults to 1."""
    nodes = sorted(g.nodes)
    index = {v: i for i, v in enumerate(nodes)}
    graph = RoadGraph((float(i), 0.0) for i in range(len(nodes)))
    for u, v, data in g.edges(data=True):
        w = weight if weight is not None else data.get("w", 1.0)
        graph.add_road(Road(index[u], index[v], w, w))
    return graph


def random_graph(n: int, m: int, seed: int, weighted: bool = False) -> nx.Graph:
    g = nx.gnm_random_graph(n, m, seed=seed)
    if weighted:
        for i, (u, v) in enumerate(g.edges):
            g[u][v]["w"] = float(1 + (i * 7 + seed) % 13)
    return g


@pytest.fixture(scope="session")
def scene():
    return build_scene(SNAPSHOT)
