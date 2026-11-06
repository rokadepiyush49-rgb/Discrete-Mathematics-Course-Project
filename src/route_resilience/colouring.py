"""Graph colouring: schedule road repairs so that no two jobs block one junction at once."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .graph import RoadGraph


def welsh_powell(adj: Sequence[set[int]]) -> list[int]:
    """Greedy colouring, highest degree first. Uses at most Δ + 1 colours."""
    colour = [-1] * len(adj)
    for v in sorted(range(len(adj)), key=lambda x: -len(adj[x])):
        taken = {colour[w] for w in adj[v]}
        c = 0
        while c in taken:
            c += 1
        colour[v] = c
    return colour


@dataclass(frozen=True, slots=True)
class RepairSchedule:
    days: list[list[int]]  # Road ids to repair on each day
    lower_bound: int  # A junction with j jobs forces at least j days
    upper_bound: int  # Δ + 1 of the conflict graph


def repair_schedule(graph: RoadGraph, road_ids: Sequence[int]) -> RepairSchedule:
    """Roads sharing a junction conflict, so this colours the line graph of the closed roads."""
    jobs_at: dict[int, list[int]] = {}
    for job, road_id in enumerate(road_ids):
        road = graph.roads[road_id]
        jobs_at.setdefault(road.u, []).append(job)
        jobs_at.setdefault(road.v, []).append(job)

    conflicts: list[set[int]] = [set() for _ in road_ids]
    for jobs in jobs_at.values():
        for a in jobs:
            conflicts[a].update(b for b in jobs if b != a)

    colour = welsh_powell(conflicts)
    days: list[list[int]] = [[] for _ in range(max(colour, default=-1) + 1)]
    for job, c in enumerate(colour):
        days[c].append(road_ids[job])
    return RepairSchedule(
        days=days,
        lower_bound=max((len(j) for j in jobs_at.values()), default=0),
        upper_bound=max((len(c) for c in conflicts), default=-1) + 1,
    )
