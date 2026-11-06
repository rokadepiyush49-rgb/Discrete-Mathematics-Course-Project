"""End-to-end tests through the real HTTP layer, on the real network."""

import pytest
from fastapi.testclient import TestClient

from route_resilience.api import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def top_junctions(client, count):
    summary = client.get("/api/summary").json()
    return [entry["vertex"] for entry in summary["criticality"]["top"][:count]]


def test_summary_has_every_section_and_no_raw_scores(client):
    body = client.get("/api/summary").json()
    assert {"area", "occlusion", "stages", "healing", "criticality", "stress"} <= set(body)
    assert "scores" not in body
    assert all(entry["holds"] for entry in body["theorems"])


def test_layers_are_valid_geojson(client):
    layers = client.get("/api/layers").json()
    assert set(layers) == {"truth", "roads", "gaps", "patches", "junctions", "pois"}
    for layer in layers.values():
        assert layer["type"] == "FeatureCollection" and layer["features"]
    kinds = {f["properties"]["kind"] for f in layers["roads"]["features"]}
    assert kinds == {"road", "stub", "healed"}


def test_closing_nothing_changes_nothing(client):
    body = client.post("/api/simulate", json={"closed": []}).json()
    assert body["index"] == {"average_path": 1.0, "efficiency": 1.0}
    assert body["stranded"] == 0 and body["components"] == 1


def test_closing_critical_junctions_hurts(client):
    body = client.post("/api/simulate", json={"closed": top_junctions(client, 5)}).json()
    assert body["index"]["efficiency"] < 1


def test_route_detours_around_a_closure(client):
    first = client.get("/api/summary").json()["criticality"]["top"][0]["vertex"]
    summary_route = {"origin": 100, "destination": 3000}
    base = client.post("/api/route", json=summary_route).json()
    closed = client.post("/api/route", json={**summary_route, "closed": [first]}).json()
    assert base["baseline"]["seconds"] == closed["baseline"]["seconds"]
    assert closed["detour"]["seconds"] >= base["baseline"]["seconds"]
    k = closed["disjoint"]["k"]
    assert k == len(closed["disjoint"]["routes"]) == len(closed["disjoint"]["cut"])


def test_route_rejects_bad_input(client):
    assert client.post("/api/route", json={"origin": 5, "destination": 5}).status_code == 422
    assert client.post("/api/route", json={"origin": -1, "destination": 5}).status_code == 422
    assert client.post("/api/simulate", json={"closed": [10**7]}).status_code == 422


def test_overlap_inclusion_exclusion_equals_direct_union(client):
    body = client.post("/api/overlap", json={"closed": top_junctions(client, 3)}).json()
    assert body["union"] == body["direct"] > 0
    assert len(body["terms"]) == 7
    assert body["union"] <= body["sum_of_singles"]


def test_response_plan_serves_or_explains_each_site(client):
    closed = top_junctions(client, 4)
    body = client.post("/api/response", json={"closed": closed}).json()
    assert len(body["assignments"]) + len(body["unserved"]) == 4
    if body["unserved"]:
        assert body["hall"]["depots"] < body["hall"]["sites"]
    schedule = body["schedule"]
    assert schedule["lower_bound"] <= len(schedule["days"]) <= schedule["upper_bound"]
    assert int(body["budget"]["affordable"]) <= int(body["budget"]["subsets"])


def test_tight_time_limit_produces_a_hall_certificate(client):
    body = client.post(
        "/api/response", json={"closed": top_junctions(client, 6), "max_minutes": 0.05}
    ).json()
    assert body["unserved"]
    assert body["hall"]["depots"] < body["hall"]["sites"]


def test_inspection_tour_is_closed_and_covers_the_sector(client):
    body = client.post("/api/inspection", json={"centre": 100, "radius_seconds": 45}).json()
    assert body["sector_roads"] > 0
    assert body["odd_vertices"] % 2 == 0
    assert body["roads"] >= body["sector_roads"]
    assert body["geometry"][0] == body["geometry"][-1]
