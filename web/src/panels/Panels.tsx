import type { Gatekeeper, HealRow, Summary } from "../api";
import { LineChart } from "../components/LineChart";
import { Callout, Formula, Prose, Section, Segmented, Stat, StatGrid, Table } from "../components/ui";
import { fixed, int, ordinal, pct } from "../format";
import type { HealMode } from "../MapView";

export function RoadsPanel({ summary }: { summary: Summary }) {
  const { area } = summary;
  const degrees = Object.entries(area.degree_counts);
  const largest = Math.max(...degrees.map(([, count]) => count));
  return (
    <>
      <Prose>
        Each junction is a vertex and each stretch of road is an edge, weighted by travel time. The
        data is real OpenStreetMap, clipped from Deccan to Camp and cut in two by the Mula-Mutha
        river.
      </Prose>
      <StatGrid>
        <Stat label="Junctions" value={int(area.junctions)} />
        <Stat label="Roads" value={int(area.roads)} />
        <Stat label="Road length" value={`${area.km.toFixed(1)} km`} />
        <Stat label="Dead ends" value={int(area.dead_ends)} />
      </StatGrid>
      <Section title="Degree of each junction">
        <ul className="space-y-1">
          {degrees.map(([degree, count]) => (
            <li key={degree} className="flex items-center gap-2 text-[13.5px]">
              <span className="w-4 font-mono text-ink-3">{degree}</span>
              <span className="h-2.5 flex-1">
                <span
                  className="block h-full rounded-r-[4px] bg-series-1"
                  style={{ width: `${Math.max((count / largest) * 100, 0.6)}%` }}
                />
              </span>
              <span className="w-12 text-right font-mono tabular-nums">{int(count)}</span>
            </li>
          ))}
        </ul>
        <Prose>
          T-junctions dominate. The sum of these degrees is exactly twice the road count, which is
          the handshake lemma.
        </Prose>
      </Section>
    </>
  );
}

export function OcclusionPanel({ summary }: { summary: Summary }) {
  const { occlusion } = summary;
  const { a, b, m, phi, family_size } = occlusion.permutation;
  return (
    <>
      <Prose>
        Tree canopy, shadow and cloud break roads in satellite masks. This simulates that damage on
        the real map, so every missing road is known and healing can be scored exactly.
      </Prose>
      <StatGrid>
        <Stat label="Roads hidden" value={int(occlusion.gaps)} tone="alert" />
        <Stat label="Fragments" value={int(occlusion.fragments)} tone="alert" />
        <Stat label="Largest fragment" value={pct(occlusion.largest_fragment)} />
        <Stat label="Canopy patches" value={occlusion.patches} />
      </StatGrid>
      <Section title="Repeatable by modular arithmetic">
        <Prose>Roads are ranked by an affine map on ℤ_m, where m is the number of roads:</Prose>
        <Formula>
          x ↦ ({a}·x + {b}) mod {m}
        </Formula>
        <Prose>
          Because gcd({a}, {m}) = 1, this is a bijection, and the extended Euclidean algorithm can
          invert it. φ({int(m)}) = {int(phi)} multipliers qualify, giving {int(family_size)} possible
          shuffles.
        </Prose>
      </Section>
    </>
  );
}

function healStats(row: HealRow) {
  return { recall: row.recall, precision: row.precision, bridges: row.links_that_are_bridges };
}

export function HealingPanel({
  summary,
  healMode,
  onMode,
}: {
  summary: Summary;
  healMode: HealMode;
  onMode: (mode: HealMode) => void;
}) {
  const row = healMode === "mst" ? summary.healing.mst : summary.healing.mst_loops;
  const stats = healStats(row);
  const stage = summary.stages[healMode === "mst" ? 2 : 3]!;
  const truth = summary.stages[0]!;
  const mst = summary.healing.mst;
  const sweep = summary.healing.sweep;
  return (
    <>
      <Segmented<HealMode>
        label="Healing method"
        value={healMode}
        onChange={onMode}
        options={[
          { value: "mst", label: "Kruskal only" },
          { value: "loops", label: "Kruskal + loops" },
        ]}
      />
      <StatGrid>
        <Stat label="Gaps found" value={pct(stats.recall)} note={`${row.correct} of ${row.true_gaps}`} />
        <Stat label="Links correct" value={pct(stats.precision)} note={`${row.correct} of ${row.links}`} />
        <Stat
          label="Independent cycles"
          value={int(stage.independent_cycles)}
          note={`of ${int(truth.independent_cycles)} in the real map`}
        />
        <Stat
          label="Travel-time error"
          value={pct(stage.mean_relative_error)}
          note="against ground truth"
        />
      </StatGrid>
      <Callout title="Every Kruskal link is a bridge">
        A link that joins two components closes no cycle, so removing it splits them again. On this
        map {mst.links_that_are_bridges} of {mst.links} Kruskal links are bridges, and the cycle
        count does not move from {int(summary.stages[1]!.independent_cycles)}. Real gaps often do
        close a cycle, so a second pass restores them.
      </Callout>
      <Section title="Each stage against the real map">
        <Table
          head={["Stage", "Parts", "Cycles", "Error"]}
          rows={summary.stages.map((s) => [
            s.name.replace("Healed: ", "").replace("MST", "Kruskal"),
            int(s.components),
            int(s.independent_cycles),
            pct(s.mean_relative_error),
          ])}
        />
        <Prose>
          The occluded error covers only the {pct(summary.stages[1]!.pairs_connected, 0)} of trips
          that can still be completed.
        </Prose>
      </Section>
      <Section title={`Repeated over ${sweep.seeds} random scenes`}>
        <Table
          head={["Measure", "Mean", "Range"]}
          rows={[
            ["Gaps found, Kruskal", pct(sweep.mst_recall.mean), ""],
            [
              "Gaps found, with loops",
              pct(sweep.full_recall.mean),
              `${pct(sweep.full_recall.min, 0)} to ${pct(sweep.full_recall.max, 0)}`,
            ],
            [
              "Links correct",
              pct(sweep.full_precision.mean),
              `${pct(sweep.full_precision.min, 0)} to ${pct(sweep.full_precision.max, 0)}`,
            ],
          ]}
        />
        <Prose>
          {sweep.lemma_held_every_time
            ? "Every Kruskal link was a bridge in all of them, as the lemma requires."
            : "The bridge lemma failed in at least one scene, which would mean a bug."}
        </Prose>
      </Section>
    </>
  );
}

export function CriticalityPanel({
  summary,
  showCuts,
  onShowCuts,
  onFocus,
}: {
  summary: Summary;
  showCuts: boolean;
  onShowCuts: (value: boolean) => void;
  onFocus: (junction: Gatekeeper) => void;
}) {
  const { criticality, counting } = summary;
  const worst = criticality.worst_cuts[0]!;
  return (
    <>
      <Prose>
        Betweenness counts how many fastest routes pass through a junction. Brandes' two recurrences
        compute it for all {int(counting.pairs)} junction pairs without listing a single path.
      </Prose>
      <StatGrid>
        <Stat label="Cut vertices" value={int(criticality.cut_vertices)} />
        <Stat label="Bridges" value={int(criticality.bridges)} />
      </StatGrid>
      <label className="flex min-h-9 cursor-pointer items-center gap-2 text-[14.5px]">
        <input
          type="checkbox"
          checked={showCuts}
          onChange={(event) => onShowCuts(event.target.checked)}
          className="size-4 accent-ink"
        />
        Show cut vertices on the map
      </label>
      <Section title="Busiest junctions">
        <ol className="-mx-2">
          {criticality.top.slice(0, 7).map((junction) => (
            <li key={junction.vertex}>
              <button
                type="button"
                onClick={() => onFocus(junction)}
                className="flex min-h-9 w-full items-center gap-2 rounded-md px-2 py-1 text-left text-[14px] hover:bg-paper"
              >
                <span className="w-5 font-mono text-ink-3">{junction.rank}</span>
                <span className="min-w-0 flex-1 truncate">{junction.name}</span>
                <span className="font-mono tabular-nums">{fixed(junction.betweenness)}</span>
              </button>
            </li>
          ))}
        </ol>
      </Section>
      <Callout title="Busy is not the same as fragile">
        Only {criticality.top50_cut_vertices} of the top 50 are cut vertices. The most damaging cut
        vertex, on {worst.name}, ranks {ordinal(worst.rank)} by betweenness, yet losing it strands{" "}
        {worst.stranded} junctions.
      </Callout>
    </>
  );
}

export function ProofsPanel({ summary }: { summary: Summary }) {
  const { theorems, percolation } = summary;
  const units: Record<number, string> = {
    1: "Unit 1: Logic and proofs",
    2: "Unit 2: Counting",
    3: "Unit 3: Advanced combinatorics",
    6: "Unit 6: Graph theory",
  };
  const passed = theorems.filter((t) => t.holds).length;
  return (
    <>
      <Stat
        label="Checked live on this network"
        value={`${passed} of ${theorems.length} hold`}
        note="Each value below is computed from the graph"
      />
      {Object.entries(units).map(([unit, title]) => (
        <Section key={unit} title={title}>
          <ul className="space-y-2.5">
            {theorems
              .filter((t) => t.unit === Number(unit))
              .map((theorem) => (
                <li key={theorem.name} className="text-[14px]">
                  <div className="flex items-start gap-1.5 font-medium">
                    <span aria-hidden="true">{theorem.holds ? "✓" : "✗"}</span>
                    <span>
                      {theorem.name}
                      <span className="sr-only">{theorem.holds ? ", holds" : ", fails"}</span>
                    </span>
                  </div>
                  <div className="pl-5 text-ink-2">{theorem.statement}</div>
                  <div className="pl-5 font-mono text-[13px] text-ink-3">{theorem.evidence}</div>
                </li>
              ))}
          </ul>
        </Section>
      ))}
      <Section title="Unit 4: A generating function, tested">
        <Prose>
          The degree generating function G₀ gives a branching factor G₁′(1) ={" "}
          {percolation.branching_factor.toFixed(2)}, so it predicts the network survives until{" "}
          {pct(percolation.predicted_critical_survival)} of junctions remain. Simulation shows it
          breaks up far earlier, near {pct(percolation.critical_survival)}.
        </Prose>
        <LineChart
          title="Largest component as random junctions survive"
          series={[
            {
              key: "lcc",
              label: "Largest component",
              color: "var(--color-series-1)",
              values: percolation.survival.map((x, i) => [x, percolation.largest_component[i]!]),
            },
          ]}
          xLabel="Junctions surviving"
          yLabel="Share in largest component"
          yDomain={[0, 1]}
          formatX={(x) => pct(x, 0)}
          formatY={(y) => pct(y, 0)}
          markers={[
            { x: percolation.predicted_critical_survival, label: "Predicted" },
            { x: percolation.critical_survival, label: "Simulated" },
          ]}
        />
        <Prose>
          The theory assumes random wiring. Roads only connect to their neighbours in space, so the
          formula is too optimistic here.
        </Prose>
      </Section>
    </>
  );
}
