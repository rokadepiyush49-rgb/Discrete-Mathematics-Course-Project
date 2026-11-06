import type { HealMode, Stage } from "../MapView";
import type { Tool } from "../panels/StressPanel";

const Line = ({ color, dashed, wide }: { color: string; dashed?: boolean; wide?: boolean }) => (
  <svg width="22" height="8" aria-hidden="true" className="shrink-0">
    <line
      x1="1"
      x2="21"
      y1="4"
      y2="4"
      stroke={color}
      strokeWidth={wide ? 4 : 2.5}
      strokeLinecap={dashed ? "butt" : "round"}
      strokeDasharray={dashed ? "4 3" : undefined}
    />
  </svg>
);

const Dot = ({ color }: { color: string }) => (
  <svg width="22" height="10" aria-hidden="true" className="shrink-0">
    <circle cx="11" cy="5" r="4" fill={color} />
  </svg>
);

const Row = ({ mark, label }: { mark: React.ReactNode; label: string }) => (
  <li className="flex items-center gap-2">
    {mark}
    {label}
  </li>
);

function HeatScale() {
  return (
    <li>
      <div
        className="h-2 w-40 rounded-full"
        style={{ background: "linear-gradient(90deg,#d9d4c7,#f3c9a0,#eb6834,#c2341d,#6e0f0a)" }}
      />
      <div className="mt-0.5 flex w-40 justify-between text-ink-3">
        <span>Few routes</span>
        <span>Many routes</span>
      </div>
    </li>
  );
}

export function Legend({
  stage,
  tool,
  healMode,
  showCuts,
  showPois,
}: {
  stage: Stage;
  tool: Tool;
  healMode: HealMode;
  showCuts: boolean;
  showPois: boolean;
}) {
  let rows: React.ReactNode;
  if (stage === "truth") {
    rows = (
      <>
        <Row mark={<Line color="#16191d" />} label="Road" />
        <Row mark={<Dot color="#2a78d6" />} label="Hospital" />
        <Row mark={<Dot color="#eb6834" />} label="Fire station" />
      </>
    );
  } else if (stage === "occlusion") {
    rows = (
      <>
        <Row mark={<Line color="#16191d" />} label="Road the satellite sees" />
        <Row mark={<Line color="#c2341d" dashed />} label="Hidden road" />
        <Row mark={<Dot color="#a6c9b3" />} label="Canopy patch" />
      </>
    );
  } else if (stage === "healing") {
    rows = (
      <>
        <Row mark={<Line color="#2a78d6" wide />} label="Kruskal link" />
        {healMode === "loops" && <Row mark={<Line color="#1baf7a" wide />} label="Loop link" />}
        <Row mark={<Line color="#16191d" dashed wide />} label="Wrong link" />
        <Row mark={<Line color="#c2341d" dashed />} label="Gap still open" />
      </>
    );
  } else {
    rows = (
      <>
        <HeatScale />
        {stage === "criticality" && showCuts && (
          <Row mark={<Dot color="#6250d6" />} label="Cut vertex" />
        )}
        {stage === "stress" && <Row mark={<Dot color="#b3261e" />} label="Closed junction" />}
        {stage === "stress" && tool === "route" && (
          <>
            <Row mark={<Line color="#16191d" dashed wide />} label="Fastest route" />
            <Row mark={<Line color="#16191d" wide />} label="Route after closures" />
            <Row mark={<Line color="#2a78d6" />} label="Road-disjoint route" />
            <Row mark={<Line color="#b3261e" wide />} label="Minimum cut" />
          </>
        )}
        {stage === "stress" && tool === "inspect" && (
          <Row mark={<Line color="#6250d6" />} label="Inspection tour" />
        )}
        {stage === "stress" && tool === "respond" && (
          <Row mark={<Line color="#2a78d6" dashed />} label="Crew assignment" />
        )}
        {stage === "stress" && showPois && (
          <>
            <Row mark={<Dot color="#2a78d6" />} label="Hospital" />
            <Row mark={<Dot color="#eb6834" />} label="Fire station" />
          </>
        )}
      </>
    );
  }
  return (
    <ul
      aria-label="Map legend"
      className="pointer-events-none absolute top-3 left-3 space-y-1 md:top-auto md:bottom-10 rounded-md bg-surface/95 px-3 py-2 text-[13px] text-ink-2 shadow-sm"
    >
      {rows}
    </ul>
  );
}
