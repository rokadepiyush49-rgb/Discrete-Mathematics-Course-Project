"""HTTP API. Serves the analysis, answers what-if questions, and hosts the built dashboard."""

from __future__ import annotations

import json
import math
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .colouring import repair_schedule
from .combinatorics import (
    budget_generating_function,
    failure_scenarios,
    inclusion_exclusion,
    surjections,
)
from .connectivity import connected_components
from .euler import inspection_tour
from .flows import edge_disjoint_routes
from .graph import LonLat, RoadGraph
from .matching import relief_plan
from .paths import shortest_path
from .pipeline import RESULTS, ROOT, Scene, _describe, build, build_scene, snap_pois
from .resilience import evaluate, resilience_index, sample_sources
from .route_hits import route_hit_sets

DIST = ROOT / "web" / "dist"
SAMPLE_SOURCES = 200
OVERLAP_SOURCES = 120
MAX_OVERLAP_CLOSURES = 5


class AppState:
    """Built once at startup. Requests only read from it."""

    def __init__(self, results_path: Path = RESULTS) -> None:
        self.scene: Scene = build_scene()
        if results_path.exists():
            self.results = json.loads(results_path.read_text())
        else:
            self.results = build(results_path)
        self.graph: RoadGraph = self.scene.graph
        self.junctions = self.scene.truth.n
        self.sources = sample_sources(self.graph, SAMPLE_SOURCES)
        self.base = evaluate(self.graph, (), self.sources)
        self.pois = snap_pois(self.graph, self.junctions)
        self.layers = build_layers(self.scene, self.results, self.pois)


state: AppState


@asynccontextmanager
async def lifespan(_: FastAPI):
    global state
    state = AppState()
    yield


app = FastAPI(title="Route Resilience", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)


# --- GeoJSON layers ------------------------------------------------------------------------


def _line(coords: tuple[LonLat, ...], **properties) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": properties,
    }


def _point(coord: LonLat, **properties) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coord},
        "properties": properties,
    }


def _circle(centre: LonLat, radius_m: float, steps: int = 40) -> dict:
    lon, lat = centre
    d_lat = math.degrees(radius_m / 6_371_008.8)
    d_lon = d_lat / math.cos(math.radians(lat))
    ring = [
        (
            lon + d_lon * math.cos(2 * math.pi * i / steps),
            lat + d_lat * math.sin(2 * math.pi * i / steps),
        )
        for i in range(steps + 1)
    ]
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {},
    }


def _collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def build_layers(scene: Scene, results: dict, pois: list[dict]) -> dict:
    graph = scene.graph
    scores = results["scores"]
    bridges = set(scores["bridges"])
    cuts = set(scores["cut_vertices"])
    road_scores = scores["road_betweenness"]
    node_scores = scores["betweenness"]
    gaps = scene.occlusion.gaps

    true_links = {frozenset((g.a, g.b)) for g in gaps}
    mst_links = set(scene.healed.mst_links)
    healed_pairs = {
        frozenset((graph.roads[i].u, graph.roads[i].v))
        for i in (*scene.healed.mst_links, *scene.healed.loop_links)
    }

    roads = []
    for road_id, road in enumerate(graph.roads):
        properties = {
            "id": road_id,
            "kind": road.kind,
            "score": round(road_scores[road_id], 6),
            "bridge": road_id in bridges,
        }
        if road.kind == "healed":
            properties["phase"] = "mst" if road_id in mst_links else "loop"
            properties["correct"] = frozenset((road.u, road.v)) in true_links
        roads.append(_line(road.geometry, **properties))

    return {
        "truth": _collection([_line(r.geometry) for r in scene.truth.roads]),
        "roads": _collection(roads),
        "gaps": _collection(
            [
                _line(
                    scene.truth.roads[g.truth_road].geometry,
                    recovered=frozenset((g.a, g.b)) in healed_pairs,
                )
                for g in gaps
            ]
        ),
        "patches": _collection([_circle(c, r) for c, r in scene.occlusion.patches]),
        "junctions": _collection(
            [
                _point(
                    graph.coords[v],
                    id=v,
                    score=round(node_scores[v], 6),
                    cut=v in cuts,
                    degree=graph.degree(v),
                    name=_describe(graph, v),
                )
                for v in range(scene.truth.n)
            ]
        ),
        "pois": _collection(
            [_point((p["lon"], p["lat"]), kind=p["kind"], name=p["name"]) for p in pois]
        ),
    }


# --- Request bodies ------------------------------------------------------------------------

type Junctions = Annotated[list[int], Field(max_length=200)]


class Closures(BaseModel):
    closed: Junctions = []


class RouteRequest(Closures):
    origin: int
    destination: int


class ResponseRequest(Closures):
    max_minutes: float = Field(default=6.0, gt=0, le=60)
    budget_hours: int = Field(default=12, ge=0, le=500)


class InspectionRequest(Closures):
    centre: int
    radius_seconds: float = Field(default=60.0, gt=0, le=240)


def _check(*vertices: int) -> None:
    for v in vertices:
        if not 0 <= v < state.junctions:
            raise HTTPException(422, f"unknown junction {v}")


def _route_geometry(graph: RoadGraph, roads: list[int], start: int) -> list[LonLat]:
    """Join road geometries end to end, flipping each to match the direction of travel."""
    points: list[LonLat] = []
    v = start
    for road_id in roads:
        road = graph.roads[road_id]
        segment = road.geometry if road.u == v else road.geometry[::-1]
        points.extend(segment if not points else segment[1:])
        v = road.other(v)
    return points


def _route_summary(found: tuple[float, list[int], list[int]] | None, start: int) -> dict | None:
    if found is None:
        return None
    seconds, _, roads = found
    return {
        "seconds": seconds,
        "metres": sum(state.graph.roads[r].length for r in roads),
        "geometry": _route_geometry(state.graph, roads, start),
    }


def _closed_roads(closed: list[int]) -> list[int]:
    return sorted({road_id for v in closed for _, road_id in state.graph.adj[v]})


# --- Endpoints -----------------------------------------------------------------------------


@app.get("/api/summary")
def summary() -> dict:
    return {key: value for key, value in state.results.items() if key != "scores"}


@app.get("/api/layers")
def layers() -> dict:
    return state.layers


@app.post("/api/simulate")
def simulate(body: Closures) -> dict:
    """What does closing these junctions cost the network?"""
    _check(*body.closed)
    closed = set(body.closed)
    after = evaluate(state.graph, closed, state.sources)
    components = connected_components(state.graph, closed)
    return {
        "state": asdict(after),
        "base": asdict(state.base),
        "index": resilience_index(state.base, after),
        "components": len(components),
        "stranded": sum(len(c) for c in components[1:]),
        "scenarios": str(failure_scenarios(state.junctions, len(closed))),
    }


@app.post("/api/route")
def route(body: RouteRequest) -> dict:
    """Fastest route before and after closures, plus Menger's disjoint routes and minimum cut."""
    _check(body.origin, body.destination, *body.closed)
    if body.origin == body.destination:
        raise HTTPException(422, "origin and destination must differ")
    graph = state.graph
    closed = set(body.closed) - {body.origin, body.destination}
    disjoint = edge_disjoint_routes(graph, body.origin, body.destination, closed)
    baseline = _route_summary(shortest_path(graph, body.origin, body.destination), body.origin)
    detour = _route_summary(
        shortest_path(graph, body.origin, body.destination, closed), body.origin
    )
    return {
        "baseline": baseline,
        "detour": detour,
        "disjoint": {
            "k": disjoint.k,
            "routes": [_route_geometry(graph, r, body.origin) for r in disjoint.routes],
            "cut": [graph.roads[r].geometry for r in disjoint.min_cut],
        },
    }


@app.post("/api/overlap")
def overlap(body: Closures) -> dict:
    """Inclusion-exclusion over the trips hit by each closure."""
    _check(*body.closed)
    closed = list(dict.fromkeys(body.closed))[:MAX_OVERLAP_CLOSURES]
    sources = state.sources[:OVERLAP_SOURCES]
    hits = route_hit_sets(state.graph, closed, sources)
    total, terms = inclusion_exclusion(hits)
    direct = len(set().union(*hits.values())) if hits else 0
    return {
        "closures": closed,
        "terms": [{"subset": list(t.subset), "size": t.size, "sign": t.sign} for t in terms],
        "union": total,
        "direct": direct,
        "sum_of_singles": sum(len(s) for s in hits.values()),
        "trips_sampled": len(sources) * (state.graph.n - 1),
    }


@app.post("/api/response")
def response(body: ResponseRequest) -> dict:
    """Assign crews with bipartite matching, and schedule repairs with graph colouring."""
    _check(*body.closed)
    closed = list(dict.fromkeys(body.closed))
    graph = state.graph
    pois = state.pois
    plan = relief_plan(graph, closed, [p["vertex"] for p in pois], closed, body.max_minutes * 60)
    roads = _closed_roads(closed)
    schedule = repair_schedule(graph, roads)

    # Longer roads take longer to repair: one crew-hour per 100 m, rounded up.
    costs = [max(1, math.ceil(graph.roads[r].length / 100)) for r in roads]
    coefficients = budget_generating_function(costs)
    affordable = sum(coefficients[: body.budget_hours + 1])
    crews = min(4, len(pois))
    return {
        "assignments": [
            {
                "site": a["site"],
                "seconds": a["seconds"],
                "name": pois[a["depot"]]["name"] or pois[a["depot"]]["kind"].replace("_", " "),
                "kind": pois[a["depot"]]["kind"],
                "from": (pois[a["depot"]]["lon"], pois[a["depot"]]["lat"]),
                "to": graph.coords[a["site"]],
            }
            for a in plan.assignments
        ],
        "unserved": plan.unserved,
        "hall": {"sites": len(plan.hall_sites), "depots": len(plan.hall_depots)},
        "schedule": {
            "days": [
                [
                    {"road": graph.roads[r].name or "Unnamed road", "metres": graph.roads[r].length}
                    for r in day
                ]
                for day in schedule.days
            ],
            "lower_bound": schedule.lower_bound,
            "upper_bound": schedule.upper_bound,
        },
        "budget": {
            "jobs": len(roads),
            "total_hours": sum(costs),
            "hours": body.budget_hours,
            "subsets": str(2 ** len(roads)),
            "affordable": str(affordable),
        },
        "crews": {
            "count": crews,
            "onto_assignments": str(surjections(len(roads), crews)) if roads else "0",
        },
    }


@app.post("/api/inspection")
def inspection(body: InspectionRequest) -> dict:
    """Chinese Postman tour of the roads around a junction."""
    _check(body.centre, *body.closed)
    closed = set(body.closed) - {body.centre}
    tour = inspection_tour(state.graph, body.centre, body.radius_seconds, closed)
    return {
        **asdict(tour),
        "geometry": _route_geometry(state.graph, tour.roads, body.centre),
        "vertices": len(tour.vertices),
        "roads": len(tour.roads),
    }


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
else:

    @app.get("/")
    def dashboard_missing() -> dict:
        return {"message": "API is running. Build the dashboard: npm --prefix web run build"}
