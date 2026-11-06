import { useCallback, useEffect, useMemo, useState } from "react";
import { get } from "./api";
import type { Coord, Gatekeeper, Layers, Summary } from "./api";
import { Legend } from "./components/Legend";
import { int, pct } from "./format";
import { MapView, type HealMode, type Overlays, type Stage } from "./MapView";
import {
  CriticalityPanel,
  HealingPanel,
  OcclusionPanel,
  ProofsPanel,
  RoadsPanel,
} from "./panels/Panels";
import { StressPanel, type Tool } from "./panels/StressPanel";

const TITLES: Record<Stage, string> = {
  truth: "Central Pune as a graph",
  occlusion: "What the satellite misses",
  healing: "Reconnecting the network",
  criticality: "Which junctions matter most",
  stress: "Stress test",
  proofs: "Theorems on real data",
};

function stageList(summary: Summary): { id: Stage; label: string; note: string }[] {
  const passed = summary.theorems.filter((t) => t.holds).length;
  return [
    { id: "truth", label: "Real roads", note: `${int(summary.area.junctions)} junctions` },
    { id: "occlusion", label: "Occlusion", note: `${int(summary.occlusion.gaps)} roads hidden` },
    { id: "healing", label: "Healing", note: `${pct(summary.healing.mst_loops.recall, 0)} found` },
    {
      id: "criticality",
      label: "Criticality",
      note: `${int(summary.criticality.cut_vertices)} cut vertices`,
    },
    { id: "stress", label: "Stress test", note: "Try it yourself" },
    { id: "proofs", label: "Proofs", note: `${passed} of ${summary.theorems.length} hold` },
  ];
}

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [layers, setLayers] = useState<Layers | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const [stage, setStage] = useState<Stage>("truth");
  const [healMode, setHealMode] = useState<HealMode>("loops");
  const [showCuts, setShowCuts] = useState(false);
  const [tool, setTool] = useState<Tool>("close");
  const [closed, setClosed] = useState<number[]>([]);
  const [origin, setOrigin] = useState<number | null>(null);
  const [destination, setDestination] = useState<number | null>(null);
  const [centre, setCentre] = useState<number | null>(null);
  const [overlays, setOverlays] = useState<Overlays>({});
  const [focus, setFocus] = useState<{ coord: Coord; junction: Gatekeeper } | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([get<Summary>("/api/summary"), get<Layers>("/api/layers")])
      .then(([s, l]) => {
        setSummary(s);
        setLayers(l);
      })
      .catch((error: Error) => setFailed(error.message));
  }, []);

  // Many junctions sit on one road, so a repeated name also carries the junction's id.
  const names = useMemo(() => {
    const features = layers?.junctions.features ?? [];
    const counts = new Map<string, number>();
    const short = (name: string) => name.split(" / ")[0]!;
    for (const feature of features) {
      const name = short(feature.properties!.name as string);
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
    const result = new Map<number, string>();
    for (const feature of features) {
      const id = feature.properties!.id as number;
      const name = short(feature.properties!.name as string);
      result.set(id, (counts.get(name) ?? 0) > 1 ? `${name} #${id}` : name);
    }
    return result;
  }, [layers]);

  const coordinates = useMemo(() => {
    const result = new Map<number, Coord>();
    for (const feature of layers?.junctions.features ?? []) {
      result.set(
        feature.properties!.id as number,
        (feature.geometry as GeoJSON.Point).coordinates as Coord,
      );
    }
    return result;
  }, [layers]);

  const pick = useCallback(
    (junction: number) => {
      if (tool === "close") {
        setClosed((list) =>
          list.includes(junction) ? list.filter((j) => j !== junction) : [...list, junction],
        );
      } else if (tool === "route") {
        if (origin === null || destination !== null) {
          setOrigin(junction);
          setDestination(null);
        } else if (junction !== origin) {
          setDestination(junction);
        }
      } else if (tool === "inspect") {
        setCentre(junction);
      }
    },
    [tool, origin, destination],
  );

  const marks = useMemo(() => {
    const items: { coord: Coord; label: string }[] = [];
    const add = (id: number | null, label: string) => {
      const coord = id === null ? undefined : coordinates.get(id);
      if (coord) items.push({ coord, label });
    };
    if (stage === "stress" && tool === "route") {
      add(origin, "Start");
      add(destination, "End");
    }
    if (stage === "stress" && tool === "inspect") add(centre, "Base");
    if (stage === "criticality" && focus) items.push({ coord: focus.coord, label: "" });
    return items;
  }, [stage, tool, origin, destination, centre, coordinates, focus]);

  const mapOverlays = useMemo(() => ({ ...overlays, points: marks }), [overlays, marks]);

  if (failed) {
    return (
      <main className="grid h-full place-items-center p-6 text-center">
        <div>
          <h1 className="text-xl font-semibold">The analysis could not be loaded</h1>
          <p className="mt-1 text-ink-2">
            Start the API with <code className="font-mono">uv run route-resilience serve</code>,
            then reload this page.
          </p>
          <p className="mt-1 font-mono text-[13px] text-ink-3">{failed}</p>
        </div>
      </main>
    );
  }

  if (!summary || !layers) {
    return (
      <main className="grid h-full place-items-center text-ink-2" role="status">
        Loading the road network
      </main>
    );
  }

  const stages = stageList(summary);
  const showPois = stage === "truth" || (stage === "stress" && tool === "respond");

  return (
    <div className="grid h-full grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)] md:grid-cols-[176px_minmax(0,1fr)_400px] md:grid-rows-1">
      <header className="flex flex-col border-b border-line bg-paper md:border-r md:border-b-0">
        <div className="px-4 pt-3 pb-2 md:pt-4 md:pb-3">
          <h1 className="text-[17px] leading-tight font-semibold">Route Resilience</h1>
          <p className="text-[13px] text-ink-3">Discrete mathematics on Pune's roads</p>
        </div>
        <nav aria-label="Pipeline stages" className="overflow-x-auto">
          <ol className="flex gap-1 px-2 pb-2 md:flex-col md:gap-0.5">
            {stages.map((item, index) => {
              const active = item.id === stage;
              return (
                <li key={item.id} className="shrink-0">
                  <button
                    type="button"
                    aria-current={active ? "step" : undefined}
                    onClick={() => setStage(item.id)}
                    className={`flex w-full items-baseline gap-2 rounded-md px-2 py-1.5 text-left transition-colors ${
                      active ? "bg-ink text-surface" : "hover:bg-line/60"
                    }`}
                  >
                    <span className={`font-mono text-[12px] ${active ? "opacity-70" : "text-ink-3"}`}>
                      {index + 1}
                    </span>
                    <span>
                      <span className="block text-[14.5px] leading-tight font-medium">
                        {item.label}
                      </span>
                      <span
                        className={`hidden text-[12.5px] md:block ${
                          active ? "opacity-75" : "text-ink-3"
                        }`}
                      >
                        {item.note}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>
      </header>

      <div className="grid min-h-0 grid-cols-[minmax(0,1fr)] grid-rows-[42%_minmax(0,1fr)] md:contents">
        <main className="relative min-h-0">
          <MapView
            layers={layers}
            summary={summary}
            stage={stage}
            healMode={healMode}
            showCuts={showCuts}
            showPois={showPois}
            closed={closed}
            overlays={mapOverlays}
            focus={focus?.coord ?? null}
            onPick={stage === "stress" && tool !== "respond" ? pick : null}
          />
          <Legend
            stage={stage}
            tool={tool}
            healMode={healMode}
            showCuts={showCuts}
            showPois={showPois}
          />
        </main>

        <aside
          aria-label={TITLES[stage]}
          className="relative min-h-0 overflow-y-auto border-t border-line bg-surface md:border-t-0 md:border-l"
        >
          <div className="space-y-4 p-4 md:p-5">
            <h2 className="text-[22px] leading-tight font-semibold">{TITLES[stage]}</h2>
            {requestError && (
              <p role="alert" className="rounded-md bg-heat-soft px-3 py-2 text-[14px] text-heat">
                The server did not answer that request. Check that the API is still running.
              </p>
            )}
            {stage === "truth" && <RoadsPanel summary={summary} />}
            {stage === "occlusion" && <OcclusionPanel summary={summary} />}
            {stage === "healing" && (
              <HealingPanel summary={summary} healMode={healMode} onMode={setHealMode} />
            )}
            {stage === "criticality" && (
              <CriticalityPanel
                summary={summary}
                showCuts={showCuts}
                onShowCuts={setShowCuts}
                onFocus={(junction) =>
                  setFocus({ coord: [junction.lon, junction.lat], junction })
                }
              />
            )}
            {stage === "stress" && (
              <StressPanel
                summary={summary}
                tool={tool}
                onTool={setTool}
                closed={closed}
                names={names}
                onClosed={setClosed}
                origin={origin}
                destination={destination}
                onClearRoute={() => {
                  setOrigin(null);
                  setDestination(null);
                }}
                centre={centre}
                onOverlays={setOverlays}
                onError={setRequestError}
              />
            )}
            {stage === "proofs" && <ProofsPanel summary={summary} />}
          </div>
        </aside>
      </div>
    </div>
  );
}
