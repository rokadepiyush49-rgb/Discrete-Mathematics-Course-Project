"""The end-to-end pipeline: real roads -> occlusion -> healing -> criticality -> stress test."""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import dijkstra as scipy_dijkstra
from scipy.spatial import cKDTree

from .centrality import brandes
from .combinatorics import failure_scenarios, percolation_estimate
from .connectivity import connected_components, cut_structure
from .graph import RoadGraph, load_snapshot
from .healing import HealMode, HealResult, heal, score_healing
from .number_theory import euler_phi
from .occlusion import OcclusionResult, occlude
from .resilience import (
    adaptive_order,
    evaluate,
    percolation_curve,
    resilience_index,
    sample_sources,
    stress_curve,
)
from .theorems import theorem_audit

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data" / "pune_core.json.gz"
RESULTS = ROOT / "artifacts" / "results.json"
SEED = 7


@dataclass(slots=True)
class Scene:
    """Everything that is cheap to rebuild deterministically from the snapshot and a seed."""

    truth: RoadGraph
    occlusion: OcclusionResult
    mst: HealResult
    healed: HealResult

    @property
    def graph(self) -> RoadGraph:
        """The network all later analysis runs on: the fully healed graph."""
        return self.healed.graph


def build_scene(snapshot: Path = SNAPSHOT, seed: int = SEED) -> Scene:
    truth = load_snapshot(snapshot)
    occlusion = occlude(truth, seed=seed)
    return Scene(
        truth=truth,
        occlusion=occlusion,
        mst=heal(occlusion.graph, HealMode.MST),
        healed=heal(occlusion.graph, HealMode.MST_LOOPS),
    )


def snap_pois(graph: RoadGraph, junctions: int) -> list[dict]:
    """Attach each hospital and fire station to its nearest junction."""
    tree = cKDTree([graph.xy(v) for v in range(junctions)])
    snapped = []
    for poi in graph.pois:
        _, vertex = tree.query(graph.project((poi["lon"], poi["lat"])))
        snapped.append({**poi, "vertex": int(vertex)})
    return snapped


def topology_error(truth: RoadGraph, candidate: RoadGraph, sources: list[int]) -> dict:
    """Compare travel times between the same junction pairs in truth and in the candidate graph.

    Original junctions keep their ids through occlusion and healing, so pairs line up exactly.
    """
    junctions = truth.n
    d_truth = scipy_dijkstra(truth.weight_matrix(), directed=False, indices=sources)
    d_cand = scipy_dijkstra(candidate.weight_matrix(), directed=False, indices=sources)
    d_cand = d_cand[:, :junctions]
    off_diagonal = d_truth > 0
    reachable = np.isfinite(d_cand) & off_diagonal
    relative = np.abs(d_cand[reachable] - d_truth[reachable]) / d_truth[reachable]
    return {
        "pairs_connected": float(reachable.sum() / off_diagonal.sum()),
        "mean_relative_error": float(relative.mean()) if relative.size else None,
    }


def _graph_row(name: str, graph: RoadGraph, truth: RoadGraph, sources: list[int]) -> dict:
    components = connected_components(graph)
    return {
        "name": name,
        "vertices": graph.n,
        "roads": graph.m,
        "components": len(components),
        "largest_component": len(components[0]) / graph.n,
        # Cycle rank is unchanged by subdividing an edge, so it compares fairly across stages.
        # The spanning tree count is not: stubs split roads, which inflates it.
        "independent_cycles": graph.m - graph.n + len(components),
        **topology_error(truth, graph, sources),
    }


def _heal_row(result: HealResult, occlusion: OcclusionResult) -> dict:
    cuts = cut_structure(result.graph)
    links = [*result.mst_links, *result.loop_links]
    return {
        **asdict(score_healing(result, occlusion.gaps)),
        "kruskal_links": len(result.mst_links),
        "loop_links": len(result.loop_links),
        "links_that_are_bridges": sum(link in cuts.bridges for link in links),
    }


def seed_sweep(truth: RoadGraph, seeds: range) -> dict:
    """Repeat occlusion and healing across seeds, to show the results are not one lucky draw."""
    rows = []
    for seed in seeds:
        occlusion = occlude(truth, seed=seed)
        mst = heal(occlusion.graph, HealMode.MST)
        full = heal(occlusion.graph, HealMode.MST_LOOPS)
        mst_score = score_healing(mst, occlusion.gaps)
        full_score = score_healing(full, occlusion.gaps)
        bridges = cut_structure(mst.graph).bridges
        rows.append(
            {
                "gaps": len(occlusion.gaps),
                "fragments": full.components_before,
                "mst_recall": mst_score.recall,
                "full_recall": full_score.recall,
                "full_precision": full_score.precision,
                "components_after": full.components_after,
                "kruskal_links": len(mst.mst_links),
                "kruskal_bridges": sum(link in bridges for link in mst.mst_links),
            }
        )

    def stats(key: str) -> dict:
        values = np.array([row[key] for row in rows], dtype=float)
        return {
            "mean": float(values.mean()),
            "sd": float(values.std(ddof=1)),
            "min": float(values.min()),
            "max": float(values.max()),
        }

    return {
        "seeds": len(rows),
        **{
            key: stats(key)
            for key in ("gaps", "fragments", "mst_recall", "full_recall", "full_precision")
        },
        "always_connected": all(row["components_after"] == 1 for row in rows),
        "lemma_held_every_time": all(
            row["kruskal_links"] == row["kruskal_bridges"] for row in rows
        ),
    }


def _stranded(graph: RoadGraph, vertex: int) -> int:
    """How many junctions lose the main network if this one goes."""
    components = connected_components(graph, {vertex})
    return sum(len(c) for c in components[1:])


def _describe(graph: RoadGraph, v: int) -> str:
    names = sorted({graph.roads[r].name for _, r in graph.adj[v] if graph.roads[r].name})
    return " / ".join(names[:2]) or f"Junction {v}"


def analyse(scene: Scene, log=print) -> dict:
    truth, occlusion, graph = scene.truth, scene.occlusion, scene.graph
    junctions = truth.n
    started = time.perf_counter()

    def step(message: str) -> None:
        log(f"[{time.perf_counter() - started:6.1f}s] {message}")

    step("Comparing graphs with ground truth")
    sources = [s % junctions for s in sample_sources(truth, 200)]
    fragmented = connected_components(occlusion.graph)
    stages = [
        _graph_row("Ground truth", truth, truth, sources),
        _graph_row("Occluded", occlusion.graph, truth, sources),
        _graph_row("Healed: MST only", scene.mst.graph, truth, sources),
        _graph_row("Healed: MST + loops", graph, truth, sources),
    ]

    step("Brandes betweenness on the healed graph")
    centrality = brandes(graph)
    step("Brandes betweenness on ground truth")
    truth_centrality = brandes(truth)

    step("Cut vertices, bridges and rank comparison")
    cuts = cut_structure(graph)
    ranking = sorted(range(junctions), key=lambda v: -centrality.nodes[v])
    truth_ranking = sorted(range(junctions), key=lambda v: -truth_centrality.nodes[v])
    top = 50
    top_set = set(ranking[:top])
    real_cuts = sorted(v for v in cuts.cut_vertices if v < junctions)
    stranded = {v: _stranded(graph, v) for v in real_cuts}
    worst_cuts = sorted(real_cuts, key=lambda v: -stranded[v])

    def gatekeeper(v: int) -> dict:
        return {
            "vertex": v,
            "name": _describe(graph, v),
            "betweenness": centrality.nodes[v],
            "rank": ranking.index(v) + 1,
            "is_cut_vertex": v in cuts.cut_vertices,
            "stranded": stranded.get(v, 0),
            "lon": graph.coords[v][0],
            "lat": graph.coords[v][1],
        }

    step("Stress tests")
    steps = 30
    sample = sample_sources(graph, 200)
    degree_order = sorted(range(junctions), key=lambda v: -graph.degree(v))
    rng = np.random.default_rng(5)
    random_curves = [
        stress_curve(graph, rng.permutation(junctions).tolist(), steps, sample) for _ in range(5)
    ]
    random_mean = [
        {
            key: float(np.mean([curve[i][key] for curve in random_curves]))
            for key in random_curves[0][i]
        }
        for i in range(steps + 1)
    ]
    step("Adaptive attack (recomputes betweenness after each removal)")
    adaptive = adaptive_order(graph, steps)
    stress = {
        "betweenness": stress_curve(graph, ranking, steps, sample),
        "adaptive": stress_curve(graph, adaptive, steps, sample),
        "degree": stress_curve(graph, degree_order, steps, sample),
        "cut_vertices": stress_curve(graph, worst_cuts, steps, sample),
        "random": random_mean,
    }

    step("Percolation: generating function against simulation")
    predicted = percolation_estimate(truth.degree(v) for v in range(truth.n))
    simulated = percolation_curve(truth)

    step("Repeating occlusion and healing across 20 seeds")
    sweep = seed_sweep(truth, range(1, 21))

    step("Theorem audit")
    mst_cuts = cut_structure(scene.mst.graph)
    audit = theorem_audit(
        graph,
        kruskal_links=len(scene.mst.mst_links),
        kruskal_bridges=sum(link in mst_cuts.bridges for link in scene.mst.mst_links),
    )

    base = evaluate(graph, (), sample)
    worst = stress["betweenness"][steps]
    step("Done")
    return {
        "area": {
            **truth.meta,
            "junctions": truth.n,
            "roads": truth.m,
            "km": sum(r.length for r in truth.roads) / 1000,
            "bridges": sum(r.bridge for r in truth.roads),
            "dead_ends": sum(truth.degree(v) == 1 for v in range(truth.n)),
            "degree_counts": dict(sorted(Counter(map(truth.degree, range(truth.n))).items())),
        },
        "occlusion": {
            "gaps": len(occlusion.gaps),
            "patches": len(occlusion.patches),
            "fragments": len(fragmented),
            "largest_fragment": len(fragmented[0]) / occlusion.graph.n,
            "permutation": {
                "m": occlusion.permutation.m,
                "a": occlusion.permutation.a,
                "b": occlusion.permutation.b,
                "phi": occlusion.phi,
                "family_size": occlusion.permutation.family_size,
            },
        },
        "stages": stages,
        "healing": {
            "mst": _heal_row(scene.mst, occlusion),
            "mst_loops": _heal_row(scene.healed, occlusion),
            "candidates": scene.healed.candidates_considered,
            "sweep": sweep,
        },
        "criticality": {
            "cut_vertices": len(real_cuts),
            "bridges": len(cuts.bridges),
            "top": [gatekeeper(v) for v in ranking[:15]],
            "worst_cuts": [gatekeeper(v) for v in worst_cuts[:10]],
            "top50_cut_vertices": len(top_set & set(real_cuts)),
            "top50_shared_with_truth": len(top_set & set(truth_ranking[:top])),
        },
        "stress": stress,
        "stress_summary": {
            "base": asdict(base),
            "after_30": worst,
            "index_after_30": resilience_index(
                base,
                evaluate(graph, ranking[:steps], sample),
            ),
        },
        "percolation": {
            "mean_degree": predicted.mean_degree,
            "branching_factor": predicted.branching_factor,
            "predicted_critical_survival": predicted.critical_survival,
            **simulated,
        },
        "counting": {
            "pairs": failure_scenarios(graph.n, 2),
            "triples": failure_scenarios(graph.n, 3),
            "phi_m": euler_phi(truth.m),
        },
        "theorems": audit,
        "scores": {
            "betweenness": centrality.nodes,
            "road_betweenness": centrality.roads,
            "cut_vertices": sorted(cuts.cut_vertices),
            "bridges": sorted(cuts.bridges),
        },
    }


def build(results: Path = RESULTS, log=print) -> dict:
    data = analyse(build_scene(), log)
    results.parent.mkdir(parents=True, exist_ok=True)
    results.write_text(json.dumps(data, ensure_ascii=False))
    log(f"Results written to {results}")
    return data
