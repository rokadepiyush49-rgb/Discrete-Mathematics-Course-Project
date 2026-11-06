import { useEffect, useMemo, useState } from "react";
import { post } from "../api";
import type {
  Inspection,
  Overlap,
  ResponsePlan,
  RouteResult,
  Simulation,
  StressPoint,
  Summary,
} from "../api";
import { LineChart } from "../components/LineChart";
import { Button, Callout, Hint, Prose, Section, Segmented, Stat, StatGrid, Table } from "../components/ui";
import { bigInt, duration, fixed, int, km, pct } from "../format";
import type { Overlays } from "../MapView";

export type Tool = "close" | "route" | "respond" | "inspect";

type Props = {
  summary: Summary;
  tool: Tool;
  onTool: (tool: Tool) => void;
  closed: number[];
  names: Map<number, string>;
  onClosed: (closed: number[]) => void;
  origin: number | null;
  destination: number | null;
  onClearRoute: () => void;
  centre: number | null;
  onOverlays: (overlays: Overlays) => void;
  onError: (message: string | null) => void;
};

/** Run a POST whenever its body changes, cancelling any request still in flight. */
function useQuery<T>(path: string, body: unknown, enabled: boolean, onError: Props["onError"]) {
  const [data, setData] = useState<T | null>(null);
  const key = JSON.stringify(body);
  useEffect(() => {
    if (!enabled) {
      setData(null);
      return;
    }
    const controller = new AbortController();
    post<T>(path, JSON.parse(key), controller.signal)
      .then((result) => {
        setData(result);
        onError(null);
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") onError(error.message);
      });
    return () => controller.abort();
  }, [path, key, enabled, onError]);
  return data;
}

const lostEfficiency = (curve: StressPoint[]) => 1 - curve[curve.length - 1]!.r_efficiency;

function ClosePanel({
  summary,
  closed,
  names,
  onClosed,
  simulation,
  overlap,
}: Pick<Props, "summary" | "closed" | "names" | "onClosed"> & {
  simulation: Simulation | null;
  overlap: Overlap | null;
}) {
  const curves = summary.stress;
  const series = [
    { key: "adaptive", label: "Adaptive", color: "var(--color-series-2)", curve: curves.adaptive },
    { key: "betweenness", label: "Betweenness", color: "var(--color-series-1)", curve: curves.betweenness },
    { key: "cut", label: "Cut vertices", color: "var(--color-series-3)", curve: curves.cut_vertices },
    { key: "random", label: "Random", color: "var(--color-series-4)", curve: curves.random },
  ].map(({ key, label, color, curve }) => ({
    key,
    label,
    color,
    values: curve.map((p): [number, number] => [p.removed, p.r_efficiency]),
  }));

  const cut = curves.cut_vertices;
  const misleading = [
    {
      key: "eff",
      label: "Efficiency",
      color: "var(--color-series-1)",
      values: cut.map((p): [number, number] => [p.removed, p.r_efficiency]),
    },
    {
      key: "path",
      label: "Path ratio",
      color: "var(--color-series-2)",
      values: cut.map((p): [number, number] => [p.removed, p.r_average_path]),
    },
  ];

  const pathRose = simulation !== null && simulation.index.average_path > 1.0005;
  const top5 = summary.criticality.top.slice(0, 5).map((j) => j.vertex);

  return (
    <>
      {closed.length === 0 ? (
        <Hint>Click junctions on the map to close them, or start with the five busiest.</Hint>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {closed.map((junction) => (
            <li key={junction}>
              <button
                type="button"
                onClick={() => onClosed(closed.filter((j) => j !== junction))}
                aria-label={`Reopen ${names.get(junction) ?? junction}`}
                className="max-w-full truncate rounded-full border border-line px-2.5 py-0.5 text-[13px] hover:bg-paper"
              >
                {names.get(junction) ?? `Junction ${junction}`} ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <Button onClick={() => onClosed(top5)}>Close the top 5</Button>
        <Button quiet disabled={closed.length === 0} onClick={() => onClosed([])}>
          Reopen all
        </Button>
      </div>
      {simulation && (
        <StatGrid>
          <Stat
            label="Efficiency index"
            value={fixed(simulation.index.efficiency)}
            tone={simulation.index.efficiency < 0.99 ? "alert" : undefined}
            note="1 means unharmed"
          />
          <Stat
            label="Path-ratio index"
            value={fixed(simulation.index.average_path)}
            note="The problem statement's R"
          />
          <Stat
            label="Stranded junctions"
            value={int(simulation.stranded)}
            tone={simulation.stranded ? "alert" : undefined}
          />
          <Stat
            label="Average trip"
            value={duration(simulation.state.average_path_s)}
            note={`was ${duration(simulation.base.average_path_s)}`}
          />
        </StatGrid>
      )}
      {pathRose && (
        <Callout title="The path ratio just improved. It should not have.">
          Stranded trips drop out of the average, so damage can raise it. The efficiency index
          counts them as lost.
        </Callout>
      )}
      {closed.length > 0 && simulation && (
        <Prose>
          This is one of {bigInt(simulation.scenarios)} ways to choose {closed.length} of{" "}
          {int(summary.area.junctions)} junctions, so C(n, k) rules out trying them all.
        </Prose>
      )}
      {overlap && overlap.closures.length >= 2 && (
        <Section title="Trips hit, by inclusion-exclusion">
          <Table
            head={["Closures in common", "Sign", "Trips"]}
            rows={overlap.terms
              .slice(0, 15)
              .map((term) => [
                term.subset.map((id) => names.get(id) ?? id).join(" ∩ "),
                term.sign > 0 ? "+" : "−",
                int(term.size),
              ])}
          />
          <Prose>
            The alternating sum gives {int(overlap.union)} trips, matching the direct union of{" "}
            {int(overlap.direct)}. Adding the closures separately would have counted{" "}
            {int(overlap.sum_of_singles)}.
          </Prose>
        </Section>
      )}
      <Section title="Which attack hurts most">
        <LineChart
          title="Efficiency index as junctions are removed"
          series={series}
          xLabel="Junctions removed"
          yLabel="Efficiency index"
          yDomain={[0.84, 1]}
          formatX={(x) => String(Math.round(x))}
          formatTick={(y) => y.toFixed(2)}
        />
        <Prose>
          After 30 closures, recomputing betweenness at each step does{" "}
          {(lostEfficiency(curves.adaptive) / lostEfficiency(curves.betweenness)).toFixed(1)} times
          the damage of the original ranking, because traffic shifts onto new junctions.
        </Prose>
      </Section>
      <Section title="Why the path ratio misleads">
        <LineChart
          title="Two indices under the cut-vertex attack"
          series={misleading}
          xLabel="Junctions removed"
          yLabel="Index"
          yDomain={[0.94, 1.02]}
          formatX={(x) => String(Math.round(x))}
          formatTick={(y) => y.toFixed(2)}
          baseline={1}
        />
      </Section>
    </>
  );
}

function RoutePanel({
  route,
  origin,
  destination,
  closed,
  onClearRoute,
}: Pick<Props, "origin" | "destination" | "closed" | "onClearRoute"> & {
  route: RouteResult | null;
}) {
  if (origin === null) return <Hint>Click a junction to set the start of the trip.</Hint>;
  if (destination === null) return <Hint>Now click a junction to set the destination.</Hint>;
  if (!route) return <Hint>Finding routes.</Hint>;

  const { baseline, detour, disjoint } = route;
  const delay = baseline && detour ? detour.seconds - baseline.seconds : null;
  return (
    <>
      <StatGrid>
        <Stat
          label="Fastest route"
          value={baseline ? duration(baseline.seconds) : "None"}
          note={baseline ? km(baseline.metres) : undefined}
        />
        <Stat
          label={closed.length ? "After closures" : "No closures yet"}
          value={detour ? duration(detour.seconds) : "No route"}
          tone={!detour || (delay ?? 0) > 0 ? "alert" : undefined}
          note={delay !== null ? `+${duration(delay)}` : "Destination is cut off"}
        />
      </StatGrid>
      <Section title="How many closures can this trip survive?">
        <Stat label="Road-disjoint routes" value={disjoint.k} />
        {disjoint.k === 0 && <Prose>These junctions are already disconnected.</Prose>}
        {disjoint.k === 1 && (
          <Prose>
            This trip has a single point of failure. Menger's theorem says one road cut is enough,
            and the road marked in red is it.
          </Prose>
        )}
        {disjoint.k > 1 && (
          <Prose>
            Each closure can break at most one of these {disjoint.k} routes. By the pigeonhole
            principle, any {disjoint.k - 1} road closure{disjoint.k === 2 ? "" : "s"} must leave a
            route open. Menger's theorem says that is tight: the {disjoint.cut.length} roads marked
            in red would cut the trip.
          </Prose>
        )}
      </Section>
      <div>
        <Button quiet onClick={onClearRoute}>
          Choose another trip
        </Button>
      </div>
    </>
  );
}

function RespondPanel({
  plan,
  closed,
  minutes,
  onMinutes,
  budget,
  onBudget,
}: {
  plan: ResponsePlan | null;
  closed: number[];
  minutes: number;
  onMinutes: (value: number) => void;
  budget: number;
  onBudget: (value: number) => void;
}) {
  if (closed.length === 0) return <Hint>Close some junctions first, then plan the response.</Hint>;
  if (!plan) return <Hint>Planning the response.</Hint>;
  return (
    <>
      <label className="block text-[14.5px]">
        Crews must arrive within <strong className="font-mono">{minutes.toFixed(1)} min</strong>
        <input
          type="range"
          min={0.5}
          max={8}
          step={0.5}
          value={minutes}
          onChange={(event) => onMinutes(Number(event.target.value))}
          className="mt-1 block h-6 w-full accent-ink"
        />
      </label>
      <Section title="Crew assignment, by bipartite matching">
        <StatGrid>
          <Stat label="Sites served" value={`${plan.assignments.length} of ${closed.length}`} />
          <Stat
            label="Unserved"
            value={plan.unserved.length}
            tone={plan.unserved.length ? "alert" : undefined}
          />
        </StatGrid>
        {plan.assignments.length > 0 && (
          <Table
            head={["Crew from", "Arrives in"]}
            rows={plan.assignments.map((a) => [a.name, duration(a.seconds)])}
          />
        )}
        {plan.unserved.length > 0 && (
          <Callout title="Hall's condition fails">
            {plan.hall.depots === 0
              ? `No crew can reach ${plan.hall.sites === 1 ? "this site" : `these ${plan.hall.sites} sites`} in time, so no assignment can serve them all. Other closures may be walling them in.`
              : `These ${plan.hall.sites} sites can reach only ${plan.hall.depots} crew${plan.hall.depots === 1 ? "" : "s"} in time. A set S with |N(S)| < |S| proves that no assignment can serve them all.`}
          </Callout>
        )}
      </Section>
      <Section title="Repair schedule, by graph colouring">
        <Prose>
          Roads that share a junction cannot be repaired on the same day. That makes each day a
          colour class of the conflict graph.
        </Prose>
        <StatGrid>
          <Stat label="Days needed" value={plan.schedule.days.length} />
          <Stat
            label="Possible range"
            value={`${plan.schedule.lower_bound} to ${plan.schedule.upper_bound}`}
            note="Busiest junction to Δ + 1"
          />
        </StatGrid>
      </Section>
      <Section title="Repair budget, by generating function">
        <label className="block text-[14.5px]">
          Budget of <strong className="font-mono">{budget} crew-hours</strong>
          <input
            type="range"
            min={0}
            max={Math.max(plan.budget.total_hours, 1)}
            value={Math.min(budget, plan.budget.total_hours)}
            onChange={(event) => onBudget(Number(event.target.value))}
            className="mt-1 block h-6 w-full accent-ink"
          />
        </label>
        <Prose>
          Expanding Π(1 + xᶜ) over the {plan.budget.jobs} closed roads shows that{" "}
          {bigInt(plan.budget.affordable)} of the {bigInt(plan.budget.subsets)} possible repair sets
          fit this budget. Finishing every road needs {plan.budget.total_hours} crew-hours.
        </Prose>
        <Prose>
          Spread over {plan.crews.count} crews with none idle, the jobs can be split{" "}
          {bigInt(plan.crews.onto_assignments)} ways, counted as onto functions.
        </Prose>
      </Section>
    </>
  );
}

function InspectPanel({
  tour,
  centre,
  seconds,
  onSeconds,
}: {
  tour: Inspection | null;
  centre: number | null;
  seconds: number;
  onSeconds: (value: number) => void;
}) {
  return (
    <>
      <Prose>
        After a disaster, a vehicle must drive every road in a sector and return. This is the Route
        Inspection problem, solved with an Euler tour.
      </Prose>
      <label className="block text-[14.5px]">
        Sector radius of <strong className="font-mono">{seconds} s</strong> of driving
        <input
          type="range"
          min={20}
          max={120}
          step={5}
          value={seconds}
          onChange={(event) => onSeconds(Number(event.target.value))}
          className="mt-1 block h-6 w-full accent-ink"
        />
      </label>
      {centre === null && <Hint>Click a junction to centre the inspection there.</Hint>}
      {tour && (
        <>
          <StatGrid>
            <Stat label="Roads in sector" value={int(tour.sector_roads)} />
            <Stat label="Odd-degree junctions" value={int(tour.odd_vertices)} note="Always even" />
            <Stat label="Road length" value={km(tour.road_length_m)} />
            <Stat
              label="Driven twice"
              value={km(tour.deadhead_m)}
              note={pct(tour.deadhead_m / tour.road_length_m, 0) + " extra"}
            />
          </StatGrid>
          <Prose>
            Odd junctions are paired by minimum-weight matching, and the paths between them are
            driven twice. Every degree is then even, so Hierholzer's algorithm can read off one
            closed tour.
          </Prose>
        </>
      )}
    </>
  );
}

export function StressPanel(props: Props) {
  const { tool, onTool, closed, origin, destination, centre, onOverlays, onError } = props;
  const [minutes, setMinutes] = useState(3);
  const [budget, setBudget] = useState(12);
  const [seconds, setSeconds] = useState(45);

  const simulation = useQuery<Simulation>("/api/simulate", { closed }, true, onError);
  const overlap = useQuery<Overlap>(
    "/api/overlap",
    { closed },
    tool === "close" && closed.length >= 2,
    onError,
  );
  const route = useQuery<RouteResult>(
    "/api/route",
    { origin, destination, closed },
    tool === "route" && origin !== null && destination !== null,
    onError,
  );
  const plan = useQuery<ResponsePlan>(
    "/api/response",
    { closed, max_minutes: minutes, budget_hours: budget },
    tool === "respond" && closed.length > 0,
    onError,
  );
  const tour = useQuery<Inspection>(
    "/api/inspection",
    { centre, closed, radius_seconds: seconds },
    tool === "inspect" && centre !== null,
    onError,
  );

  const overlays = useMemo<Overlays>(() => {
    if (tool === "route" && route) {
      return {
        baseline: route.baseline?.geometry,
        detour: closed.length ? route.detour?.geometry : undefined,
        disjoint: route.disjoint.routes,
        cut: route.disjoint.cut,
      };
    }
    if (tool === "respond" && plan) {
      return { relief: plan.assignments.map((a) => [a.from, a.to]) };
    }
    if (tool === "inspect" && tour) return { tour: tour.geometry };
    return {};
  }, [tool, route, plan, tour, closed.length]);

  useEffect(() => onOverlays(overlays), [overlays, onOverlays]);

  return (
    <>
      <Segmented<Tool>
        label="Stress test tool"
        value={tool}
        onChange={onTool}
        options={[
          { value: "close", label: "Close" },
          { value: "route", label: "Route" },
          { value: "respond", label: "Respond" },
          { value: "inspect", label: "Inspect" },
        ]}
      />
      {tool === "close" && <ClosePanel {...props} simulation={simulation} overlap={overlap} />}
      {tool === "route" && <RoutePanel {...props} route={route} />}
      {tool === "respond" && (
        <RespondPanel
          plan={plan}
          closed={closed}
          minutes={minutes}
          onMinutes={setMinutes}
          budget={budget}
          onBudget={setBudget}
        />
      )}
      {tool === "inspect" && (
        <InspectPanel tour={tour} centre={centre} seconds={seconds} onSeconds={setSeconds} />
      )}
    </>
  );
}
