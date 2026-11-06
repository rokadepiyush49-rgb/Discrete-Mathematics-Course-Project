import {
  AttributionControl,
  LngLatBounds,
  Map as MapLibre,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type StyleSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { useEffect, useRef, useState } from "react";
import type { Coord, Layers, Summary } from "./api";

export type Stage = "truth" | "occlusion" | "healing" | "criticality" | "stress" | "proofs";
export type HealMode = "mst" | "loops";

export type Overlays = {
  detour?: Coord[];
  baseline?: Coord[];
  disjoint?: Coord[][];
  cut?: Coord[][];
  tour?: Coord[];
  relief?: [Coord, Coord][];
  points?: { coord: Coord; label: string }[];
};

type Props = {
  layers: Layers;
  summary: Summary;
  stage: Stage;
  healMode: HealMode;
  showCuts: boolean;
  showPois: boolean;
  closed: number[];
  overlays: Overlays;
  focus: Coord | null;
  onPick: ((junction: number) => void) | null;
};

// MapLibre 6 is ESM-only, and the bundler has to be told where the worker file ended up.
setWorkerUrl(workerUrl);

const BASEMAP = "https://tiles.openfreemap.org/styles/positron";
const PLAIN_MAP: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "paper", type: "background", paint: { "background-color": "#f4f1ea" } }],
};

const HEAT: ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["get", "score"],
  0,
  "#d9d4c7",
  0.004,
  "#f3c9a0",
  0.02,
  "#eb6834",
  0.06,
  "#c2341d",
  0.14,
  "#6e0f0a",
];

const HEAT_WIDTH: ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["get", "score"],
  0,
  0.8,
  0.02,
  2,
  0.14,
  5,
];

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

const lines = (paths: Coord[][]): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: paths
    .filter((path) => path.length > 1)
    .map((coordinates, index) => ({
      type: "Feature",
      properties: { index },
      geometry: { type: "LineString", coordinates },
    })),
});

const points = (items: { coord: Coord; label: string }[]): GeoJSON.FeatureCollection => ({
  type: "FeatureCollection",
  features: items.map((item) => ({
    type: "Feature",
    properties: { label: item.label },
    geometry: { type: "Point", coordinates: item.coord },
  })),
});

function addLayers(map: MapLibre, layers: Layers) {
  const firstLabel = map.getStyle().layers?.find((layer) => layer.type === "symbol")?.id;

  map.addSource("truth", { type: "geojson", data: layers.truth });
  map.addSource("roads", { type: "geojson", data: layers.roads });
  map.addSource("gaps", { type: "geojson", data: layers.gaps });
  map.addSource("patches", { type: "geojson", data: layers.patches });
  map.addSource("junctions", { type: "geojson", data: layers.junctions });
  map.addSource("pois", { type: "geojson", data: layers.pois });
  for (const id of ["closed", "baseline", "detour", "disjoint", "cut", "tour", "relief", "marks"]) {
    map.addSource(id, { type: "geojson", data: EMPTY });
  }

  map.addLayer(
    {
      id: "patches",
      type: "fill",
      source: "patches",
      paint: { "fill-color": "#2f7d4f", "fill-opacity": 0.16 },
    },
    firstLabel,
  );
  map.addLayer(
    {
      id: "truth",
      type: "line",
      source: "truth",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#16191d", "line-width": 1.1, "line-opacity": 0.8 },
    },
    firstLabel,
  );
  map.addLayer(
    {
      id: "fragments",
      type: "line",
      source: "roads",
      filter: ["!=", ["get", "kind"], "healed"],
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#16191d", "line-width": 1.1, "line-opacity": 0.8 },
    },
    firstLabel,
  );
  map.addLayer(
    {
      id: "heat",
      type: "line",
      source: "roads",
      layout: { "line-cap": "round", "line-join": "round", "line-sort-key": ["get", "score"] },
      paint: { "line-color": HEAT, "line-width": HEAT_WIDTH },
    },
    firstLabel,
  );
  map.addLayer({
    id: "gaps",
    type: "line",
    source: "gaps",
    paint: { "line-color": "#c2341d", "line-width": 2, "line-dasharray": [1.2, 1.2] },
  });
  map.addLayer({
    id: "links",
    type: "line",
    source: "roads",
    filter: ["==", ["get", "kind"], "healed"],
    layout: { "line-cap": "round" },
    paint: {
      "line-color": ["match", ["get", "phase"], "mst", "#2a78d6", "#1baf7a"],
      "line-width": 3.5,
    },
  });
  map.addLayer({
    id: "wrong-links",
    type: "line",
    source: "roads",
    filter: ["all", ["==", ["get", "kind"], "healed"], ["==", ["get", "correct"], false]],
    paint: { "line-color": "#16191d", "line-width": 3.5, "line-dasharray": [0.8, 0.8] },
  });
  map.addLayer({
    id: "disjoint",
    type: "line",
    source: "disjoint",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": [
        "match",
        ["%", ["get", "index"], 4],
        0,
        "#2a78d6",
        1,
        "#1baf7a",
        2,
        "#eda100",
        "#6250d6",
      ],
      "line-width": 3,
      "line-opacity": 0.75,
    },
  });
  map.addLayer({
    id: "baseline",
    type: "line",
    source: "baseline",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#16191d", "line-width": 4, "line-dasharray": [1.4, 1.2] },
  });
  map.addLayer({
    id: "detour",
    type: "line",
    source: "detour",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#16191d", "line-width": 4 },
  });
  map.addLayer({
    id: "cut",
    type: "line",
    source: "cut",
    layout: { "line-cap": "round" },
    paint: { "line-color": "#b3261e", "line-width": 7 },
  });
  map.addLayer({
    id: "tour",
    type: "line",
    source: "tour",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#6250d6", "line-width": 3 },
  });
  map.addLayer({
    id: "relief",
    type: "line",
    source: "relief",
    paint: { "line-color": "#2a78d6", "line-width": 2, "line-dasharray": [2, 1.5] },
  });
  map.addLayer({
    id: "junction-dots",
    type: "circle",
    source: "junctions",
    minzoom: 13,
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 13, 1.2, 16, 4],
      "circle-color": "#16191d",
      "circle-opacity": 0.5,
    },
  });
  map.addLayer({
    id: "cut-vertices",
    type: "circle",
    source: "junctions",
    filter: ["==", ["get", "cut"], true],
    paint: {
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 2, 16, 6],
      "circle-color": "#6250d6",
      "circle-stroke-color": "#fcfcfb",
      "circle-stroke-width": 1,
    },
  });
  map.addLayer({
    id: "pois",
    type: "circle",
    source: "pois",
    paint: {
      "circle-radius": ["match", ["get", "kind"], "fire_station", 6, 4],
      "circle-color": ["match", ["get", "kind"], "fire_station", "#eb6834", "#2a78d6"],
      "circle-stroke-color": "#fcfcfb",
      "circle-stroke-width": 1.5,
    },
  });
  map.addLayer({
    id: "junction-hit",
    type: "circle",
    source: "junctions",
    paint: { "circle-radius": 9, "circle-opacity": 0 },
  });
  map.addLayer({
    id: "closed",
    type: "circle",
    source: "closed",
    paint: {
      "circle-radius": 7,
      "circle-color": "#b3261e",
      "circle-stroke-color": "#fcfcfb",
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: "marks",
    type: "circle",
    source: "marks",
    paint: {
      "circle-radius": 7,
      "circle-color": "#16191d",
      "circle-stroke-color": "#fcfcfb",
      "circle-stroke-width": 2,
    },
  });
}

function visibility(stage: Stage, showCuts: boolean, showPois: boolean): Record<string, boolean> {
  const fragmented = stage === "occlusion" || stage === "healing";
  const analysed = stage === "criticality" || stage === "stress" || stage === "proofs";
  return {
    truth: stage === "truth",
    patches: fragmented,
    fragments: fragmented,
    gaps: fragmented,
    links: stage === "healing",
    "wrong-links": stage === "healing",
    heat: analysed,
    "cut-vertices": stage === "criticality" && showCuts,
    "junction-dots": stage === "stress",
    "junction-hit": stage === "stress",
    pois: stage === "truth" || showPois,
    closed: stage === "stress",
    baseline: stage === "stress",
    detour: stage === "stress",
    disjoint: stage === "stress",
    cut: stage === "stress",
    tour: stage === "stress",
    relief: stage === "stress",
    marks: stage === "stress" || stage === "criticality",
  };
}

export function MapView(props: Props) {
  const { layers, summary, stage, healMode, showCuts, showPois, closed, overlays, focus, onPick } =
    props;
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibre | null>(null);
  const pick = useRef(onPick);
  const [ready, setReady] = useState(false);
  const [basemapFailed, setBasemapFailed] = useState(false);

  pick.current = onPick;

  useEffect(() => {
    let map: MapLibre | undefined;
    let cancelled = false;

    (async () => {
      let style: StyleSpecification | string = PLAIN_MAP;
      try {
        const response = await fetch(BASEMAP, { signal: AbortSignal.timeout(5000) });
        if (response.ok) style = BASEMAP;
        else setBasemapFailed(true);
      } catch {
        setBasemapFailed(true);
      }
      if (cancelled || !container.current) return;

      const [west, south, east, north] = summary.area.bbox;
      map = new MapLibre({
        container: container.current,
        style,
        bounds: [
          [west, south],
          [east, north],
        ],
        fitBoundsOptions: { padding: 20 },
        attributionControl: false,
        maxZoom: 18,
        minZoom: 11,
      });
      map.addControl(
        new AttributionControl({
          compact: window.innerWidth < 768,
          customAttribution: "Road data © OpenStreetMap contributors",
        }),
      );
      map.addControl(new NavigationControl({ showCompass: false }), "top-right");
      map.addControl(new ScaleControl({ unit: "metric" }), "bottom-right");
      mapRef.current = map;

      map.on("load", () => {
        if (!map) return;
        addLayers(map, layers);
        setReady(true);
      });

      const nearestJunction = (x: number, y: number) => {
        const found = map!.queryRenderedFeatures(
          [
            [x - 10, y - 10],
            [x + 10, y + 10],
          ],
          { layers: ["junction-hit"] },
        );
        let best: number | null = null;
        let bestDistance = Infinity;
        for (const feature of found) {
          const [lon, lat] = (feature.geometry as GeoJSON.Point).coordinates as Coord;
          const screen = map!.project([lon, lat]);
          const distance = Math.hypot(screen.x - x, screen.y - y);
          if (distance < bestDistance) {
            bestDistance = distance;
            best = feature.properties.id as number;
          }
        }
        return best;
      };

      map.on("click", (event) => {
        if (!pick.current) return;
        const junction = nearestJunction(event.point.x, event.point.y);
        if (junction !== null) pick.current(junction);
      });
      map.on("mousemove", (event) => {
        const active = pick.current && nearestJunction(event.point.x, event.point.y) !== null;
        map!.getCanvas().style.cursor = active ? "pointer" : "";
      });
    })();

    return () => {
      cancelled = true;
      map?.remove();
      mapRef.current = null;
      setReady(false);
    };
    // The map is created once. Later changes reach it through the effects below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    for (const [id, visible] of Object.entries(visibility(stage, showCuts, showPois))) {
      map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
    }
    // Healing stage: Kruskal-only shows blue links. Otherwise show both passes.
    const onlyKruskal = healMode === "mst";
    map.setFilter(
      "links",
      onlyKruskal
        ? ["all", ["==", ["get", "kind"], "healed"], ["==", ["get", "phase"], "mst"]]
        : ["==", ["get", "kind"], "healed"],
    );
    map.setFilter(
      "wrong-links",
      onlyKruskal
        ? [
            "all",
            ["==", ["get", "kind"], "healed"],
            ["==", ["get", "correct"], false],
            ["==", ["get", "phase"], "mst"],
          ]
        : ["all", ["==", ["get", "kind"], "healed"], ["==", ["get", "correct"], false]],
    );
    map.setFilter(
      "gaps",
      stage === "healing" && !onlyKruskal ? ["==", ["get", "recovered"], false] : null,
    );
  }, [ready, stage, healMode, showCuts, showPois]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const source = (id: string) => map.getSource(id) as GeoJSONSource;
    const byId = new Map(
      layers.junctions.features.map((f) => [
        f.properties!.id as number,
        (f.geometry as GeoJSON.Point).coordinates as Coord,
      ]),
    );
    source("closed").setData(
      points(closed.flatMap((id) => (byId.has(id) ? [{ coord: byId.get(id)!, label: "" }] : []))),
    );
    source("baseline").setData(lines(overlays.baseline ? [overlays.baseline] : []));
    source("detour").setData(lines(overlays.detour ? [overlays.detour] : []));
    source("disjoint").setData(lines(overlays.disjoint ?? []));
    source("cut").setData(lines(overlays.cut ?? []));
    source("tour").setData(lines(overlays.tour ? [overlays.tour] : []));
    source("relief").setData(lines((overlays.relief ?? []).map(([a, b]) => [a, b])));
    source("marks").setData(points(overlays.points ?? []));
  }, [ready, closed, overlays, layers]);

  // An inspection sector is only a few streets, so bring it into view.
  useEffect(() => {
    const tour = overlays.tour;
    if (!ready || !tour || tour.length < 2) return;
    const bounds = tour.reduce(
      (box, coord) => box.extend(coord),
      new LngLatBounds(tour[0], tour[0]),
    );
    mapRef.current?.fitBounds(bounds, { padding: 90, maxZoom: 16.5, duration: 700 });
  }, [ready, overlays.tour]);

  useEffect(() => {
    if (ready && focus) mapRef.current?.flyTo({ center: focus, zoom: 15.5, duration: 700 });
  }, [ready, focus]);

  return (
    <div className="relative h-full w-full bg-paper">
      <div ref={container} className="h-full w-full" />
      {basemapFailed && (
        <div className="absolute top-3 left-3 rounded-md bg-surface/90 px-2.5 py-1 text-[13px] text-ink-2 shadow-sm">
          Basemap unavailable. Showing the road graph only.
        </div>
      )}
    </div>
  );
}
