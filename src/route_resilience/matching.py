"""Bipartite matching: which crew goes to which damaged junction."""

from __future__ import annotations

from collections import deque
from collections.abc import Collection, Sequence
from dataclasses import dataclass

from .graph import RoadGraph
from .paths import dijkstra

UNMATCHED = -1


def hopcroft_karp(adj: Sequence[Sequence[int]], n_right: int) -> tuple[list[int], list[int]]:
    """Maximum bipartite matching. adj[left] lists the right vertices it may match.

    Each phase finds a maximal set of shortest augmenting paths. By Berge's theorem, a matching
    is maximum exactly when no augmenting path remains.
    """
    n_left = len(adj)
    match_left = [UNMATCHED] * n_left
    match_right = [UNMATCHED] * n_right

    while True:
        # BFS layers from all free left vertices.
        layer = [-1] * n_left
        queue = deque()
        for v in range(n_left):
            if match_left[v] == UNMATCHED:
                layer[v] = 0
                queue.append(v)
        reachable_free = False
        while queue:
            v = queue.popleft()
            for w in adj[v]:
                partner = match_right[w]
                if partner == UNMATCHED:
                    reachable_free = True
                elif layer[partner] == -1:
                    layer[partner] = layer[v] + 1
                    queue.append(partner)
        if not reachable_free:
            return match_left, match_right

        for v in range(n_left):
            if match_left[v] == UNMATCHED:
                _augment(v, adj, layer, match_left, match_right)


def _augment(
    v: int,
    adj: Sequence[Sequence[int]],
    layer: list[int],
    match_left: list[int],
    match_right: list[int],
) -> bool:
    """Depth-first search for an augmenting path that follows the BFS layers."""
    for w in adj[v]:
        partner = match_right[w]
        if partner == UNMATCHED or (
            layer[partner] == layer[v] + 1
            and _augment(partner, adj, layer, match_left, match_right)
        ):
            match_left[v] = w
            match_right[w] = v
            return True
    layer[v] = -1
    return False


def hall_violator(
    adj: Sequence[Sequence[int]], match_left: Sequence[int], match_right: Sequence[int]
) -> tuple[set[int], set[int]]:
    """When left vertices go unmatched, return a set S with |N(S)| < |S|.

    Hall's theorem says such a set must exist. It is the set of left vertices reachable from a
    free left vertex by alternating paths, and N(S) is the right vertices reached on the way.
    """
    left = {v for v, w in enumerate(match_left) if w == UNMATCHED}
    right: set[int] = set()
    stack = list(left)
    while stack:
        for w in adj[stack.pop()]:
            if w not in right:
                right.add(w)
                partner = match_right[w]
                if partner != UNMATCHED and partner not in left:
                    left.add(partner)
                    stack.append(partner)
    return left, right


@dataclass(frozen=True, slots=True)
class ReliefPlan:
    assignments: list[dict]  # site, depot index, travel seconds
    unserved: list[int]
    hall_sites: list[int]  # S, when some site cannot be served
    hall_depots: list[int]  # N(S)


def relief_plan(
    graph: RoadGraph,
    sites: Sequence[int],
    depots: Sequence[int],
    closed: Collection[int],
    max_seconds: float,
) -> ReliefPlan:
    """Send one crew per site. A crew may reach a site, but not pass through a closed junction."""
    closed_set = set(closed)
    depot_ids = list(range(len(depots)))
    adj: list[list[int]] = []
    seconds: list[dict[int, float]] = []
    for site in sites:
        distance, _, _ = dijkstra(graph, site, closed_set - {site})
        times = {d: distance[depots[d]] for d in depot_ids if distance[depots[d]] <= max_seconds}
        seconds.append(times)
        adj.append(sorted(times, key=times.__getitem__))  # Nearest first

    match_left, match_right = hopcroft_karp(adj, len(depots))
    assignments = [
        {"site": sites[i], "depot": d, "seconds": seconds[i][d]}
        for i, d in enumerate(match_left)
        if d != UNMATCHED
    ]
    unserved = [sites[i] for i, d in enumerate(match_left) if d == UNMATCHED]
    if unserved:
        s, n_s = hall_violator(adj, match_left, match_right)
        return ReliefPlan(assignments, unserved, [sites[i] for i in sorted(s)], sorted(n_s))
    return ReliefPlan(assignments, [], [], [])
