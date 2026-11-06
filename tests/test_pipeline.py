"""Properties of the pipeline on the real Pune network."""

import math

import networkx as nx
from conftest import from_networkx
from hypothesis import given, settings
from hypothesis import strategies as st

from route_resilience.combinatorics import inclusion_exclusion, log10_spanning_trees
from route_resilience.connectivity import connected_components, cut_structure
from route_resilience.dsu import DisjointSet
from route_resilience.graph import Road, RoadGraph
from route_resilience.healing import (
    HealMode,
    alignment_angle,
    heal,
    passes_gate,
    score_healing,
)
from route_resilience.occlusion import cut_polyline, occlude
from route_resilience.resilience import (
    evaluate,
    percolation_curve,
    resilience_index,
    sample_sources,
)
from route_resilience.route_hits import route_hit_sets
from route_resilience.theorems import theorem_audit


def test_snapshot_is_a_connected_simple_graph(scene):
    truth = scene.truth
    assert len(connected_components(truth)) == 1
    pairs = [frozenset((r.u, r.v)) for r in truth.roads]
    assert len(pairs) == len(set(pairs))  # No parallel edges
    assert all(len(p) == 2 for p in pairs)  # No self-loops


def test_occlusion_is_reproducible(scene):
    again = occlude(scene.truth)
    assert [(g.truth_road, g.a, g.b) for g in again.gaps] == [
        (g.truth_road, g.a, g.b) for g in scene.occlusion.gaps
    ]


def test_a_different_seed_gives_a_different_scene(scene):
    other = occlude(scene.truth, seed=8)
    assert {g.truth_road for g in other.gaps} != {g.truth_road for g in scene.occlusion.gaps}


def test_each_gap_leaves_two_dangling_ends(scene):
    graph = scene.occlusion.graph
    for gap in scene.occlusion.gaps:
        assert graph.degree(gap.a) == graph.degree(gap.b) == 1


def test_cut_polyline_keeps_the_lengths_it_should():
    line = ((73.80, 18.50), (73.81, 18.50))
    head, tail = cut_polyline(line, 100.0, 500.0)
    assert head[0] == line[0] and tail[-1] == line[1]
    assert head[-1][0] < tail[0][0]


def test_healing_reconnects_everything(scene):
    assert scene.healed.components_before > 100
    assert scene.healed.components_after == 1
    assert len(connected_components(scene.graph)) == 1


def test_lemma_every_kruskal_link_is_a_bridge_on_real_data(scene):
    bridges = cut_structure(scene.mst.graph).bridges
    assert scene.mst.mst_links
    assert all(link in bridges for link in scene.mst.mst_links)


@settings(max_examples=40, deadline=None)
@given(st.integers(0, 10_000), st.integers(4, 18))
def test_lemma_every_kruskal_link_is_a_bridge_on_random_forests(seed, n):
    g = nx.gnm_random_graph(n, n // 2, seed=seed)
    graph = from_networkx(g)
    dsu = DisjointSet(n)
    for road in graph.roads:
        dsu.union(road.u, road.v)

    links = []
    candidates = sorted(((a * 31 + b * 17 + seed) % 97, a, b) for a in range(n) for b in range(a))
    for _, a, b in candidates:
        if dsu.union(a, b):
            links.append(graph.add_road(Road(a, b, 1.0, 1.0)))
    bridges = cut_structure(graph).bridges
    assert all(link in bridges for link in links)
    assert dsu.count == 1


def test_loop_pass_beats_mst_on_recall_and_removes_bridges(scene):
    mst = score_healing(scene.mst, scene.occlusion.gaps)
    full = score_healing(scene.healed, scene.occlusion.gaps)
    assert full.recall > 2 * mst.recall
    assert full.precision > 0.8


def test_subdivision_preserves_cycle_rank_but_inflates_spanning_trees():
    cycle = from_networkx(nx.cycle_graph(4))
    longer = from_networkx(nx.cycle_graph(8))  # The same loop with every edge subdivided
    assert cycle.m - cycle.n == longer.m - longer.n
    assert log10_spanning_trees(longer) > log10_spanning_trees(cycle)


def test_gate_is_a_conjunction():
    truth_table = [(100, 10, True), (100, 90, False), (500, 10, False), (500, 90, False)]
    for distance, angle, expected in truth_table:
        assert passes_gate(distance, angle, 120, 50) == expected


def test_alignment_of_collinear_and_perpendicular_ends():
    east, west, north = (1.0, 0.0), (-1.0, 0.0), (0.0, 1.0)
    assert alignment_angle((0, 0), east, (10, 0), west) == 0
    assert math.isclose(alignment_angle((0, 0), north, (10, 0), west), 90)


def test_healing_on_a_toy_gap():
    coords = [(0.0, 0.0), (0.0005, 0.0), (0.0008, 0.0), (0.0013, 0.0)]
    graph = RoadGraph(coords)
    graph.add_road(Road(0, 1, 55, 5, geometry=(coords[0], coords[1])))
    graph.add_road(Road(2, 3, 55, 5, geometry=(coords[2], coords[3])))
    healed = heal(graph, HealMode.MST)
    assert healed.components_before == 2 and healed.components_after == 1
    assert len(healed.mst_links) == 1


def test_efficiency_and_index_are_well_defined_after_disconnection():
    graph = from_networkx(nx.path_graph(5))
    base = evaluate(graph)
    cut = evaluate(graph, {2})
    assert cut.reachable_pairs < 1
    index = resilience_index(base, cut)
    assert 0 < index["efficiency"] < 1
    # The average-path index rises here: the long trips simply stopped being counted.
    assert index["average_path"] > 1


def test_evaluate_matches_networkx_efficiency():
    g = nx.petersen_graph()
    graph = from_networkx(g)
    assert math.isclose(evaluate(graph).efficiency, nx.global_efficiency(g))
    assert math.isclose(evaluate(graph).average_path_s, nx.average_shortest_path_length(g))


def test_percolation_curve_rises_to_one():
    curve = percolation_curve(from_networkx(nx.grid_2d_graph(30, 30)), runs=5)
    assert curve["largest_component"][-1] == 1
    assert curve["largest_component"] == sorted(curve["largest_component"])
    assert 0.4 < curve["critical_survival"] < 0.8  # Square-lattice site percolation is ~0.593


def test_inclusion_exclusion_on_real_route_hits(scene):
    graph = scene.graph
    sources = sample_sources(graph, 40)
    closures = [109, 210, 199]
    hits = route_hit_sets(graph, closures, sources)
    total, _ = inclusion_exclusion(hits)
    assert total == len(set().union(*hits.values()))
    assert total > 0


def test_every_audited_theorem_holds_on_the_healed_network(scene):
    bridges = cut_structure(scene.mst.graph).bridges
    audit = theorem_audit(
        scene.graph,
        kruskal_links=len(scene.mst.mst_links),
        kruskal_bridges=sum(link in bridges for link in scene.mst.mst_links),
    )
    assert len(audit) >= 15
    failed = [entry["name"] for entry in audit if not entry["holds"]]
    assert not failed
