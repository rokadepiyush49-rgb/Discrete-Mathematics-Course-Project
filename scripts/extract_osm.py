"""Turn a raw OpenStreetMap .osm.pbf file into the compact road snapshot used by the project.

OSM stores a road as a "way": a long list of points that may run through many junctions.
A graph needs one edge per junction-to-junction stretch, so this script does the same job
as a street-network library, by hand:

1. Keep drivable ways that enter the bounding box, and cut them where they leave it.
2. A point is a graph vertex if it ends a way or is shared by two or more ways.
3. Split every way at its vertices. Each piece becomes an edge with its full geometry.

Usage (needs the optional `data` dependency group):

    uv run --group data python scripts/extract_osm.py western-zone.osm.pbf \
        --bbox 73.835,18.455,73.885,18.535 --out data/pune_core.json.gz
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

import osmium

DRIVABLE = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link",
    "secondary", "secondary_link", "tertiary", "tertiary_link", "unclassified",
    "residential", "living_street",
}  # fmt: skip
BLOCKED_ACCESS = {"private", "no"}
POI_AMENITIES = {"hospital", "fire_station"}


class Collector(osmium.SimpleHandler):
    def __init__(self, bbox: tuple[float, float, float, float]) -> None:
        super().__init__()
        self.bbox = bbox
        self.ways: list[dict] = []
        self.pois: list[dict] = []

    def inside(self, lon: float, lat: float) -> bool:
        west, south, east, north = self.bbox
        return west <= lon <= east and south <= lat <= north

    def node(self, n) -> None:
        amenity = n.tags.get("amenity")
        if amenity in POI_AMENITIES and n.location.valid():
            lon, lat = n.location.lon, n.location.lat
            if self.inside(lon, lat):
                self.pois.append(
                    {"kind": amenity, "name": n.tags.get("name", ""), "lon": lon, "lat": lat}
                )

    def way(self, w) -> None:
        tags = w.tags
        amenity = tags.get("amenity")
        if amenity in POI_AMENITIES:
            points = [(p.location.lon, p.location.lat) for p in w.nodes if p.location.valid()]
            if points:
                lon = sum(p[0] for p in points) / len(points)
                lat = sum(p[1] for p in points) / len(points)
                if self.inside(lon, lat):
                    self.pois.append(
                        {"kind": amenity, "name": tags.get("name", ""), "lon": lon, "lat": lat}
                    )
            return

        highway = tags.get("highway")
        if highway not in DRIVABLE or tags.get("area") == "yes":
            return
        if tags.get("access") in BLOCKED_ACCESS or tags.get("motor_vehicle") in BLOCKED_ACCESS:
            return

        # Cut the way into runs of consecutive in-box points.
        run: list[tuple[int, float, float]] = []
        runs = [run]
        for p in w.nodes:
            if not p.location.valid():
                continue
            lon, lat = p.location.lon, p.location.lat
            if self.inside(lon, lat):
                run.append((p.ref, round(lon, 6), round(lat, 6)))
            elif run:
                run = []
                runs.append(run)
        for points in runs:
            if len(points) >= 2:
                self.ways.append(
                    {
                        "points": points,
                        "highway": highway,
                        "name": tags.get("name", ""),
                        "maxspeed": tags.get("maxspeed", ""),
                        "bridge": tags.get("bridge", "no") not in {"no", ""},
                    }
                )


def split_into_edges(ways: list[dict]) -> tuple[dict[int, tuple[float, float]], list[dict]]:
    """Split ways at vertices: way endpoints, plus points shared by two or more ways."""
    uses: Counter[int] = Counter()
    for way in ways:
        refs = [p[0] for p in way["points"]]
        uses.update(refs)
        # An endpoint counts twice, so it always qualifies as a vertex.
        uses[refs[0]] += 1
        uses[refs[-1]] += 1

    vertices: dict[int, tuple[float, float]] = {}
    edges: list[dict] = []
    for way in ways:
        points = way["points"]
        start = 0
        for i in range(1, len(points)):
            if uses[points[i][0]] >= 2:
                piece = points[start : i + 1]
                u, v = piece[0][0], piece[-1][0]
                vertices[u] = (piece[0][1], piece[0][2])
                vertices[v] = (piece[-1][1], piece[-1][2])
                edges.append(
                    {
                        "u": u,
                        "v": v,
                        "highway": way["highway"],
                        "name": way["name"],
                        "maxspeed": way["maxspeed"],
                        "bridge": way["bridge"],
                        "geometry": [[p[1], p[2]] for p in piece],
                    }
                )
                start = i
    return vertices, edges


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pbf", type=Path)
    parser.add_argument("--bbox", required=True, help="west,south,east,north in degrees")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", default="Central Pune")
    args = parser.parse_args()

    bbox = tuple(float(x) for x in args.bbox.split(","))
    collector = Collector(bbox)
    collector.apply_file(str(args.pbf), locations=True, idx="flex_mem")
    vertices, edges = split_into_edges(collector.ways)

    # Compact ids keep the committed snapshot small.
    index = {osm_id: i for i, osm_id in enumerate(vertices)}
    snapshot = {
        "meta": {
            "label": args.label,
            "bbox": bbox,
            "source": "OpenStreetMap via Geofabrik (western-zone extract)",
            "license": "ODbL 1.0, © OpenStreetMap contributors",
        },
        "nodes": [[lon, lat] for lon, lat in vertices.values()],
        "edges": [{**e, "u": index[e["u"]], "v": index[e["v"]]} for e in edges],
        "pois": collector.pois,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(filename=args.out, mode="wb", mtime=0) as f:
        f.write(json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False).encode())
    size_kb = args.out.stat().st_size / 1024
    print(
        f"{args.label}: {len(vertices)} vertices, {len(edges)} edges, "
        f"{len(collector.pois)} POIs -> {args.out} ({size_kb:.0f} KiB)"
    )


if __name__ == "__main__":
    main()
