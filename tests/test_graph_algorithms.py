import itertools

import networkx as nx
import pytest
from conftest import from_networkx, random_graph
from hypothesis import given, settings
from hypothesis import strategies as st

from route_resilience.centrality import brandes
from route_resilience.colouring import repair_schedule, welsh_powell
from route_resilience.connectivity import connected_components, cut_structure, two_colouring
from route_resilience.dsu import DisjointSet
from route_resilience.euler import hierholzer, inspection_tour
from route_resilience.flows import edge_disjoint_routes
from route_resilience.graph import Road, RoadGraph
from route_resilience.matching import hall_violator, hopcroft_karp
from route_resilience.paths import dijkstra, shortest_path

graphs = st.tuples(st.integers(2, 28), st.integers(0, 70), st.integers(0, 10_000))


def build(params, weighted=False):
    n, m, seed = params
    return random_graph(n, min(m, n * (n - 1) // 2), seed, weighted)


@given(st.integers(1, 40), st.lists(st.tuples(st.integers(0, 39), st.integers(0, 39))))
def test_dsu_classes_match_connected_components(n, pairs):
    dsu = DisjointSet(n)
    g = nx.empty_graph(n)
    for a, b in pairs:
        if a < n and b < n:
            dsu.union(a, b)
            g.add_edge(a, b)
    assert {frozenset(c) for c in dsu.classes()} == {
        frozenset(c) for c in nx.connected_components(g)
    }
    assert dsu.count == nx.number_connected_components(g)


@given(st.integers(2, 30), st.lists(st.tuples(st.integers(0, 29), st.integers(0, 29))))
def test_connectivity_is_an_equivalence_relation(n, pairs):
    dsu = DisjointSet(n)
    for a, b in pairs:
        if a < n and b < n:
            dsu.union(a, b)
    same = dsu.same
    for a in range(n):
        assert same(a, a)  # Reflexive
        for b in range(n):
            assert same(a, b) == same(b, a)  # Symmetric
            for c in range(n):
                if same(a, b) and same(b, c):
                    assert same(a, c)  # Transitive


@settings(max_examples=60)
@given(graphs)
def test_dijkstra_matches_networkx(params):
    g = build(params, weighted=True)
    graph = from_networkx(g)
    dist, _, _ = dijkstra(graph, 0)
    expected = nx.single_source_dijkstra_path_length(g, 0, weight="w")
    for v in range(graph.n):
        if v in expected:
            assert dist[v] == expected[v]
        else:
            assert dist[v] == float("inf")


@settings(max_examples=60)
@given(graphs)
def test_brandes_matches_networkx_on_unweighted_graphs_with_ties(params):
    g = build(params)
    graph = from_networkx(g)
    result = brandes(graph)
    expected = nx.betweenness_centrality(g, normalized=True)
    for v in range(graph.n):
        assert result.nodes[v] == pytest.approx(expected[v], abs=1e-9)
    edges = nx.edge_betweenness_centrality(g, normalized=True)
    for road_id, road in enumerate(graph.roads):
        value = edges.get((road.u, road.v), edges.get((road.v, road.u)))
        assert result.roads[road_id] == pytest.approx(value, abs=1e-9)


@settings(max_examples=60)
@given(graphs)
def test_brandes_matches_networkx_on_weighted_graphs(params):
    g = build(params, weighted=True)
    graph = from_networkx(g)
    expected = nx.betweenness_centrality(g, weight="w", normalized=True)
    result = brandes(graph)
    for v in range(graph.n):
        assert result.nodes[v] == pytest.approx(expected[v], abs=1e-9)


def test_star_centre_has_full_betweenness():
    assert brandes(from_networkx(nx.star_graph(6))).nodes[0] == pytest.approx(1.0)


@settings(max_examples=80)
@given(graphs)
def test_tarjan_matches_networkx(params):
    g = build(params)
    graph = from_networkx(g)
    cuts = cut_structure(graph)
    assert cuts.cut_vertices == set(nx.articulation_points(g))
    found = {frozenset((graph.roads[r].u, graph.roads[r].v)) for r in cuts.bridges}
    assert found == {frozenset(e) for e in nx.bridges(g)}


@settings(max_examples=80)
@given(graphs)
def test_two_colouring_matches_networkx_and_witness_is_an_odd_cycle(params):
    g = build(params)
    graph = from_networkx(g)
    bipartite, witness = two_colouring(graph)
    assert bipartite == nx.is_bipartite(g)
    if not bipartite:
        assert witness[0] == witness[-1]
        assert (len(witness) - 1) % 2 == 1
        assert all(g.has_edge(a, b) for a, b in itertools.pairwise(witness))


@settings(max_examples=80)
@given(graphs)
def test_menger_routes_are_disjoint_and_cut_matches(params):
    g = build(params)
    graph = from_networkx(g)
    s, t = 0, graph.n - 1
    result = edge_disjoint_routes(graph, s, t)
    assert result.k == (nx.edge_connectivity(g, s, t) if nx.has_path(g, s, t) else 0)
    assert len(result.min_cut) == result.k  # Max-flow min-cut

    used = [road for route in result.routes for road in route]
    assert len(used) == len(set(used))  # Edge-disjoint
    for route in result.routes:
        v = s
        for road_id in route:
            road = graph.roads[road_id]
            assert v in (road.u, road.v)
            v = road.other(v)
        assert v == t

    # Closing the cut separates s from t.
    cut = {frozenset((graph.roads[r].u, graph.roads[r].v)) for r in result.min_cut}
    h = g.copy()
    h.remove_edges_from(tuple(e) for e in cut)
    assert not nx.has_path(h, s, t)


@settings(max_examples=120)
@given(graphs, st.randoms(use_true_random=False))
def test_pigeonhole_any_k_minus_1_closures_leave_the_endpoints_connected(params, rng):
    g = build(params)
    graph = from_networkx(g)
    s, t = 0, graph.n - 1
    k = edge_disjoint_routes(graph, s, t).k
    if k == 0:
        return
    h = g.copy()
    h.remove_edges_from(rng.sample(list(g.edges), k - 1))  # Any k - 1 roads at all
    assert nx.has_path(h, s, t)


def test_euler_tour_on_an_even_multigraph():
    edges = [(0, 1), (1, 2), (2, 0), (0, 3), (3, 4), (4, 0)]
    steps = hierholzer(edges, 0)
    assert steps[0] == (0, -1) and steps[-1][0] == 0
    assert sorted(e for _, e in steps[1:]) == list(range(len(edges)))
    for (a, _), (b, e) in itertools.pairwise(steps):
        assert {a, b} == set(edges[e])


@settings(max_examples=25, deadline=None)
@given(st.integers(0, 10_000))
def test_inspection_tour_covers_every_road_in_a_closed_walk(seed):
    g = nx.gnm_random_graph(14, 26, seed=seed)
    g = g.subgraph(max(nx.connected_components(g), key=len)).copy()
    graph = from_networkx(g)
    tour = inspection_tour(graph, 0, radius_s=1e9)
    assert tour.vertices[0] == tour.vertices[-1] == 0
    assert set(tour.roads) == set(range(graph.m))
    for i, road_id in enumerate(tour.roads):  # Consecutive steps really are joined by that road
        road = graph.roads[road_id]
        assert {tour.vertices[i], tour.vertices[i + 1]} == {road.u, road.v}
    assert tour.odd_vertices % 2 == 0  # Handshake corollary


@settings(max_examples=100)
@given(st.integers(1, 12), st.integers(1, 12), st.integers(0, 40), st.integers(0, 10_000))
def test_hopcroft_karp_size_and_hall_certificate(a, b, m, seed):
    g = nx.bipartite.gnmk_random_graph(a, b, m, seed=seed)
    adj = [[w - a for w in g[v]] for v in range(a)]
    match_left, match_right = hopcroft_karp(adj, b)

    expected = nx.bipartite.maximum_matching(g, top_nodes=range(a))
    assert sum(w != -1 for w in match_left) == len(expected) // 2

    for v, w in enumerate(match_left):
        if w != -1:
            assert w in adj[v] and match_right[w] == v

    if -1 in match_left:
        s, n_s = hall_violator(adj, match_left, match_right)
        assert len(n_s) < len(s)  # Hall's condition fails on this witness
        assert {w for v in s for w in adj[v]} <= n_s


@settings(max_examples=60)
@given(graphs)
def test_greedy_colouring_is_proper_and_within_delta_plus_one(params):
    g = build(params)
    adj = [set(g[v]) for v in sorted(g.nodes)]
    colour = welsh_powell(adj)
    assert all(colour[u] != colour[v] for u, v in g.edges)
    delta = max((len(s) for s in adj), default=0)
    assert max(colour) + 1 <= delta + 1


def test_repair_schedule_keeps_jobs_at_a_junction_apart():
    graph = RoadGraph((float(i), 0.0) for i in range(5))
    for u, v in ((0, 1), (0, 2), (0, 3), (3, 4)):
        graph.add_road(Road(u, v, 1, 1))
    schedule = repair_schedule(graph, [0, 1, 2, 3])
    assert schedule.lower_bound == 3 <= len(schedule.days) <= schedule.upper_bound
    for day in schedule.days:
        ends = [x for r in day for x in (graph.roads[r].u, graph.roads[r].v)]
        assert len(ends) == len(set(ends))


def test_shortest_path_reroutes_around_a_block():
    g = nx.cycle_graph(6)
    graph = from_networkx(g)
    assert shortest_path(graph, 0, 2)[0] == 2
    assert shortest_path(graph, 0, 2, blocked={1})[0] == 4
    assert shortest_path(graph, 0, 2, blocked={1, 5}) is None


def test_components_respect_removed_vertices():
    graph = from_networkx(nx.path_graph(5))
    assert sorted(map(len, connected_components(graph, {2}))) == [2, 2]
