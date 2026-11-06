"""Topological healing: reconnect a fragmented road graph.

Two passes run over the same candidate links.

Pass 1 is Kruskal's algorithm, with a Disjoint Set seeded from the fragmented graph. It adds a
link only if the link joins two different components, which yields a minimum spanning forest of
the contracted graph and connects everything it can at least cost.

Pass 1 has a built-in weakness (Lemma 3 in the report): every link it adds is a bridge, because
it never closes a cycle. A real road gap often *does* close a cycle. Pass 2 therefore restores
those by accepting strictly aligned links between unused dangling ends of the same component.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from .dsu import DisjointSet
from .graph import Road as RoadEdge
from .graph import RoadGraph, haversine_m, travel_seconds
from .number_theory import CRTGrid
from .occlusion import Gap


class HealMode(StrEnum):
    MST = "mst"
    MST_LOOPS = "mst+loops"


@dataclass(frozen=True, slots=True)
class Candidate:
    cost: float
    a: int
    b: int
    distance: float
    angle: float


@dataclass(slots=True)
class HealResult:
    graph: RoadGraph
    mst_links: list[int] = field(default_factory=list)  # Road ids in the healed graph
    loop_links: list[int] = field(default_factory=list)
    candidates_considered: int = 0
    components_before: int = 0
    components_after: int = 0


def outward_direction(graph: RoadGraph, v: int) -> tuple[float, float]:
    """Unit vector pointing out of the road end at dangling vertex v."""
    _, road_id = graph.adj[v][0]
    road = graph.roads[road_id]
    points = road.geometry if road.v == v else road.geometry[::-1]
    # Walk back along the road a little, so that tiny final segments do not skew the heading.
    end = graph.project(points[-1])
    inner = end
    for p in reversed(points[:-1]):
        inner = graph.project(p)
        if math.dist(inner, end) >= 8:
            break
    dx, dy = end[0] - inner[0], end[1] - inner[1]
    norm = math.hypot(dx, dy) or 1.0
    return dx / norm, dy / norm


def alignment_angle(
    a_xy: tuple[float, float],
    a_dir: tuple[float, float],
    b_xy: tuple[float, float],
    b_dir: tuple[float, float],
) -> float:
    """Worst deviation, in degrees, between either road end and the straight link joining them."""
    dx, dy = b_xy[0] - a_xy[0], b_xy[1] - a_xy[1]
    norm = math.hypot(dx, dy) or 1.0
    ux, uy = dx / norm, dy / norm
    cos_a = max(-1.0, min(1.0, a_dir[0] * ux + a_dir[1] * uy))
    cos_b = max(-1.0, min(1.0, -(b_dir[0] * ux + b_dir[1] * uy)))
    return math.degrees(max(math.acos(cos_a), math.acos(cos_b)))


def passes_gate(distance: float, angle: float, max_gap: float, max_angle: float) -> bool:
    """The acceptance rule as a proposition: (distance ≤ D) ∧ (angle ≤ Θ)."""
    return distance <= max_gap and angle <= max_angle


def find_candidates(graph: RoadGraph, max_gap: float, max_angle: float) -> list[Candidate]:
    """All dangling-end pairs that pass the gate, cheapest first.

    Ends are binned into grid cells of side max_gap, so only the 3×3 block around a cell needs
    checking, rather than all pairs.
    """
    ends = [v for v in range(graph.n) if graph.degree(v) == 1]
    positions = {v: graph.xy(v) for v in ends}
    directions = {v: outward_direction(graph, v) for v in ends}

    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    min_x, min_y = min(xs), min(ys)
    side = int(max(max(xs) - min_x, max(ys) - min_y) / max_gap) + 3
    grid = CRTGrid(side)

    def cell(v: int) -> tuple[int, int]:
        x, y = positions[v]
        return int((y - min_y) / max_gap) + 1, int((x - min_x) / max_gap) + 1

    buckets: dict[int, list[int]] = {}
    for v in ends:
        buckets.setdefault(grid.key(*cell(v)), []).append(v)

    found = []
    for a in ends:
        row, col = cell(a)
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                for b in buckets.get(grid.key(row + dr, col + dc), ()):
                    if b <= a:
                        continue
                    distance = math.dist(positions[a], positions[b])
                    angle = alignment_angle(
                        positions[a], directions[a], positions[b], directions[b]
                    )
                    if passes_gate(distance, angle, max_gap, max_angle):
                        cost = distance * (1 + angle / 45)
                        found.append(Candidate(cost, a, b, distance, angle))
    found.sort(key=lambda c: (c.cost, c.a, c.b))
    return found


def _add_link(graph: RoadGraph, candidate: Candidate) -> int:
    a, b = candidate.a, candidate.b
    highway = graph.roads[graph.adj[a][0][1]].highway
    length = haversine_m(graph.coords[a], graph.coords[b])
    return graph.add_road(
        RoadEdge(
            a, b, length, travel_seconds(length, highway), highway,
            graph.roads[graph.adj[a][0][1]].name, False,
            (graph.coords[a], graph.coords[b]), kind="healed",
        )
    )  # fmt: skip


def heal(
    fragmented: RoadGraph,
    mode: HealMode = HealMode.MST_LOOPS,
    max_gap: float = 120.0,
    max_angle: float = 50.0,
    strict_angle: float = 25.0,
) -> HealResult:
    graph = fragmented.copy()
    candidates = find_candidates(graph, max_gap, max_angle)

    dsu = DisjointSet(graph.n)
    for road in graph.roads:
        dsu.union(road.u, road.v)
    result = HealResult(
        graph=graph, candidates_considered=len(candidates), components_before=dsu.count
    )

    # Pass 1: Kruskal. A dangling end continues into one road, so each end is used at most once.
    used: set[int] = set()
    for c in candidates:
        if c.a in used or c.b in used:
            continue
        if dsu.union(c.a, c.b):  # Invariant: the added links always form a forest on components.
            used.update((c.a, c.b))
            result.mst_links.append(_add_link(graph, c))

    # Closure: a curved road can fail the alignment gate and strand a fragment. Connectivity
    # outranks alignment here, so retry between separate components with the angle test off.
    if dsu.count > 1:
        for c in find_candidates(graph, max_gap * 1.5, 180.0):
            if dsu.union(c.a, c.b):
                used.update((c.a, c.b))
                result.mst_links.append(_add_link(graph, c))

    # Pass 2: close the loops that Kruskal must, by construction, refuse.
    if mode is HealMode.MST_LOOPS:
        for c in candidates:
            if c.a in used or c.b in used or c.angle > strict_angle:
                continue
            used.update((c.a, c.b))
            result.loop_links.append(_add_link(graph, c))

    result.components_after = dsu.count
    return result


@dataclass(frozen=True, slots=True)
class HealScore:
    true_gaps: int
    links: int
    correct: int
    precision: float
    recall: float


def score_healing(result: HealResult, gaps: list[Gap]) -> HealScore:
    """Compare healed links with the known gaps. A link is right if it joins a gap's two ends."""
    truth = {frozenset((g.a, g.b)) for g in gaps}
    made = [
        frozenset((result.graph.roads[i].u, result.graph.roads[i].v))
        for i in (*result.mst_links, *result.loop_links)
    ]
    correct = sum(link in truth for link in made)
    return HealScore(
        true_gaps=len(truth),
        links=len(made),
        correct=correct,
        precision=correct / len(made) if made else 0.0,
        recall=correct / len(truth) if truth else 1.0,
    )
