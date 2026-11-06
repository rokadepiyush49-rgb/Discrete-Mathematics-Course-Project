"""The road network as a simple undirected weighted graph.

Vertices are junctions and dead ends. Edges are stretches of road between them, weighted by
travel time in seconds. One-way restrictions are ignored, so the model is undirected.
"""

from __future__ import annotations

import gzip
import itertools
import json
import math
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from scipy import sparse

EARTH_RADIUS_M = 6_371_008.8

# Assumed free-flow speeds for dense urban Pune, in km/h. OSM speed tags are too sparse to use.
SPEED_KPH = {
    "motorway": 60, "motorway_link": 40, "trunk": 40, "trunk_link": 30,
    "primary": 35, "primary_link": 25, "secondary": 30, "secondary_link": 22,
    "tertiary": 25, "tertiary_link": 20, "unclassified": 20, "residential": 18,
    "living_street": 12,
}  # fmt: skip
DEFAULT_SPEED_KPH = 20

type LonLat = tuple[float, float]


def travel_seconds(length_m: float, highway: str) -> float:
    return length_m / (SPEED_KPH.get(highway, DEFAULT_SPEED_KPH) / 3.6)


def haversine_m(a: LonLat, b: LonLat) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def polyline_length_m(points: list[LonLat]) -> float:
    return sum(haversine_m(p, q) for p, q in itertools.pairwise(points))


@dataclass(slots=True)
class Road:
    """An edge. `kind` is "road" (original), "stub" (survived occlusion) or "healed"."""

    u: int
    v: int
    length: float
    time: float
    highway: str = "unclassified"
    name: str = ""
    bridge: bool = False
    geometry: tuple[LonLat, ...] = ()
    kind: str = "road"

    def other(self, x: int) -> int:
        return self.v if x == self.u else self.u


class RoadGraph:
    """Adjacency-list graph. Road ids are stable, so results can refer to them."""

    def __init__(self, coords: Iterable[LonLat] = (), roads: Iterable[Road] = ()) -> None:
        self.coords: list[LonLat] = list(coords)
        self.roads: list[Road] = []
        self.adj: list[list[tuple[int, int]]] = [[] for _ in self.coords]
        self.pois: list[dict] = []
        self.meta: dict = {}
        for road in roads:
            self.add_road(road)

    @property
    def n(self) -> int:
        return len(self.coords)

    @property
    def m(self) -> int:
        return len(self.roads)

    def add_node(self, coord: LonLat) -> int:
        self.coords.append(coord)
        self.adj.append([])
        return self.n - 1

    def add_road(self, road: Road) -> int:
        road_id = len(self.roads)
        self.roads.append(road)
        self.adj[road.u].append((road.v, road_id))
        self.adj[road.v].append((road.u, road_id))
        return road_id

    def degree(self, v: int) -> int:
        return len(self.adj[v])

    def copy(self) -> RoadGraph:
        clone = RoadGraph(self.coords, (replace(r) for r in self.roads))
        clone.pois = self.pois
        clone.meta = self.meta
        return clone

    def weights(self, attribute: str = "time") -> list[float]:
        return [getattr(r, attribute) for r in self.roads]

    def xy(self, v: int) -> tuple[float, float]:
        """Local planar coordinates in metres (equirectangular, fine at city scale)."""
        return self.project(self.coords[v])

    def project(self, coord: LonLat) -> tuple[float, float]:
        lon0, lat0 = self.origin
        x = math.radians(coord[0] - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
        y = math.radians(coord[1] - lat0) * EARTH_RADIUS_M
        return x, y

    @property
    def origin(self) -> LonLat:
        return self.coords[0]

    # --- Matrix representations (syllabus Unit 6) ---------------------------------------

    def adjacency_matrix(self) -> sparse.csr_array:
        """A[i, j] = 1 when i and j are joined by a road."""
        rows = [r.u for r in self.roads] + [r.v for r in self.roads]
        cols = [r.v for r in self.roads] + [r.u for r in self.roads]
        data = np.ones(len(rows), dtype=np.int64)
        return sparse.coo_array((data, (rows, cols)), shape=(self.n, self.n)).tocsr()

    def incidence_matrix(self) -> sparse.csr_array:
        """B[v, e] = 1 when vertex v is an end of edge e."""
        rows = [r.u for r in self.roads] + [r.v for r in self.roads]
        cols = list(range(self.m)) * 2
        data = np.ones(len(rows), dtype=np.int64)
        return sparse.coo_array((data, (rows, cols)), shape=(self.n, self.m)).tocsr()

    def weight_matrix(self, removed: Iterable[int] = ()) -> sparse.csr_array:
        """Travel-time matrix with the `removed` vertices cut out, for SciPy's solvers."""
        dead = np.zeros(self.n, dtype=bool)
        dead[list(removed)] = True
        u = np.fromiter((r.u for r in self.roads), dtype=np.int32, count=self.m)
        v = np.fromiter((r.v for r in self.roads), dtype=np.int32, count=self.m)
        w = np.fromiter((r.time for r in self.roads), dtype=np.float64, count=self.m)
        keep = ~(dead[u] | dead[v])
        u, v, w = u[keep], v[keep], w[keep]
        return sparse.coo_array(
            (np.r_[w, w], (np.r_[u, v], np.r_[v, u])), shape=(self.n, self.n)
        ).tocsr()


def _contract_degree_two(coords: list[LonLat], roads: dict[tuple[int, int], Road]) -> None:
    """Merge the two roads at a vertex of degree 2. Such a vertex is not a real junction."""
    incident: dict[int, set[tuple[int, int]]] = {}
    for key in roads:
        for end in key:
            incident.setdefault(end, set()).add(key)

    queue = deque(v for v, keys in incident.items() if len(keys) == 2)
    while queue:
        w = queue.popleft()
        keys = incident.get(w, ())
        if len(keys) != 2:
            continue
        k1, k2 = keys
        r1, r2 = roads[k1], roads[k2]
        a, b = r1.other(w), r2.other(w)
        new_key = (min(a, b), max(a, b))
        if a == b or new_key in roads:
            continue  # Merging would create a loop or a parallel edge.

        g1 = r1.geometry if r1.v == w else r1.geometry[::-1]  # a -> w
        g2 = r2.geometry if r2.u == w else r2.geometry[::-1]  # w -> b
        merged = Road(
            a, b, r1.length + r2.length, r1.time + r2.time,
            r1.highway, r1.name or r2.name, r1.bridge or r2.bridge, g1 + g2[1:],
        )  # fmt: skip
        del roads[k1], roads[k2]
        roads[new_key] = merged
        del incident[w]
        incident[a].discard(k1)
        incident[b].discard(k2)
        incident[a].add(new_key)
        incident[b].add(new_key)
        queue.extend((a, b))


def load_snapshot(path: Path) -> RoadGraph:
    """Read the OSM snapshot and return its largest connected component as a simple graph."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        raw = json.load(f)
    coords: list[LonLat] = [tuple(c) for c in raw["nodes"]]

    roads: dict[tuple[int, int], Road] = {}
    for e in raw["edges"]:
        u, v = e["u"], e["v"]
        if u == v:
            continue  # A self-loop would stop the graph being simple.
        geometry = tuple(tuple(p) for p in e["geometry"])
        length = polyline_length_m(list(geometry))
        road = Road(
            u, v, length, travel_seconds(length, e["highway"]),
            e["highway"], e["name"], e["bridge"], geometry,
        )  # fmt: skip
        key = (min(u, v), max(u, v))
        if key not in roads or road.time < roads[key].time:
            roads[key] = road  # Of parallel edges, the fastest stands for the pair.

    _contract_degree_two(coords, roads)

    # Keep the largest component, then renumber vertices 0..n-1.
    neighbours: dict[int, list[int]] = {}
    for u, v in roads:
        neighbours.setdefault(u, []).append(v)
        neighbours.setdefault(v, []).append(u)
    seen: set[int] = set()
    best: list[int] = []
    for start in neighbours:
        if start in seen:
            continue
        seen.add(start)
        comp, stack = [start], [start]
        while stack:
            for w in neighbours[stack.pop()]:
                if w not in seen:
                    seen.add(w)
                    comp.append(w)
                    stack.append(w)
        if len(comp) > len(best):
            best = comp

    index = {old: new for new, old in enumerate(sorted(best))}
    graph = RoadGraph(coords[old] for old in sorted(best))
    for road in roads.values():
        if road.u in index:
            road.u, road.v = index[road.u], index[road.v]
            graph.add_road(road)
    graph.pois = raw["pois"]
    graph.meta = raw["meta"]
    return graph
