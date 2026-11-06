"""Simulate what satellite road extraction loses under tree canopy, shadow and cloud.

Each occluded road keeps two short stubs, as a broken segmentation mask would, and loses its
middle. The result is a fragmented graph with a known answer: we know exactly which gaps exist,
so healing can be scored precisely.

Which roads are hit is decided by an affine permutation of Z_m (see number_theory.py), so a
seed always reproduces the same scene.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .graph import LonLat, RoadGraph, haversine_m, travel_seconds
from .graph import Road as RoadEdge
from .number_theory import AffinePermutation, euler_phi

MIN_OCCLUDABLE_M = 40.0
MAX_GAP_M = 90.0
GAP_FRACTION = 0.6


@dataclass(frozen=True, slots=True)
class Gap:
    """One hidden stretch of road between two dangling ends."""

    truth_road: int
    a: int
    b: int
    length: float


@dataclass(slots=True)
class OcclusionResult:
    graph: RoadGraph
    gaps: list[Gap]
    patches: list[tuple[LonLat, float]]
    permutation: AffinePermutation
    phi: int = 0
    road_of_gap_end: dict[int, int] = field(default_factory=dict)


def cut_polyline(
    points: tuple[LonLat, ...], start_m: float, end_m: float
) -> tuple[tuple[LonLat, ...], tuple[LonLat, ...]]:
    """Return the parts of a polyline before start_m and after end_m."""

    def locate(target: float) -> tuple[int, LonLat]:
        walked = 0.0
        for i in range(len(points) - 1):
            step = haversine_m(points[i], points[i + 1])
            if walked + step >= target and step > 0:
                t = (target - walked) / step
                p, q = points[i], points[i + 1]
                return i, (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
            walked += step
        return len(points) - 2, points[-1]

    i, first_cut = locate(start_m)
    j, second_cut = locate(end_m)
    return (*points[: i + 1], first_cut), (second_cut, *points[j + 1 :])


def occlude(
    truth: RoadGraph,
    seed: int = 7,
    patches: int = 40,
    patch_radius_m: float = 260.0,
    coverage: float = 0.55,
    clutter: float = 0.02,
) -> OcclusionResult:
    """Hide roads inside canopy patches, plus a thin scatter of random clutter."""
    edge_perm = AffinePermutation.from_seed(truth.m, seed)
    node_perm = AffinePermutation.from_seed(truth.n, seed + 1)
    centres = [truth.coords[node_perm(i)] for i in range(patches)]
    centres_xy = [truth.project(c) for c in centres]

    def in_patch(road: RoadEdge) -> bool:
        mid = road.geometry[len(road.geometry) // 2]
        x, y = truth.project(mid)
        return any(math.hypot(x - cx, y - cy) <= patch_radius_m for cx, cy in centres_xy)

    graph = RoadGraph(truth.coords)
    graph.pois, graph.meta = truth.pois, truth.meta
    gaps: list[Gap] = []
    for road_id, road in enumerate(truth.roads):
        rank = edge_perm(road_id) / truth.m  # Uniform in [0, 1), and every value distinct.
        chance = coverage if in_patch(road) else clutter
        if road.length < MIN_OCCLUDABLE_M or rank >= chance:
            graph.add_road(
                RoadEdge(
                    road.u, road.v, road.length, road.time, road.highway, road.name,
                    road.bridge, road.geometry,
                )
            )  # fmt: skip
            continue

        gap_length = min(road.length * GAP_FRACTION, MAX_GAP_M)
        stub = (road.length - gap_length) / 2
        head, tail = cut_polyline(road.geometry, stub, road.length - stub)
        a = graph.add_node(head[-1])
        b = graph.add_node(tail[0])
        for u, v, geometry in ((road.u, a, head), (b, road.v, tail)):
            graph.add_road(
                RoadEdge(
                    u, v, stub, travel_seconds(stub, road.highway), road.highway, road.name,
                    road.bridge, geometry, kind="stub",
                )
            )  # fmt: skip
        gaps.append(Gap(road_id, a, b, gap_length))

    return OcclusionResult(
        graph=graph,
        gaps=gaps,
        patches=[(c, patch_radius_m) for c in centres],
        permutation=edge_perm,
        phi=euler_phi(truth.m),
    )
