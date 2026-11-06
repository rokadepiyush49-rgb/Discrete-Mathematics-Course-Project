import { useEffect, useMemo, useRef, useState } from "react";
import { Table } from "./ui";

export type Series = { key: string; label: string; color: string; values: [number, number][] };
export type Marker = { x: number; label: string };

type Props = {
  title: string;
  series: Series[];
  xLabel: string;
  yLabel: string;
  yDomain: [number, number];
  formatX?: (x: number) => string;
  formatY?: (y: number) => string;
  formatTick?: (y: number) => string;
  markers?: Marker[];
  baseline?: number;
};

const HEIGHT = 230;
const MARGIN = { top: 14, bottom: 34, left: 40 };

export function LineChart({
  title,
  series,
  xLabel,
  yLabel,
  yDomain,
  formatX = String,
  formatY = (y) => y.toFixed(3),
  formatTick = formatY,
  markers = [],
  baseline,
}: Props) {
  const frame = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(360);
  const [cursor, setCursor] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  useEffect(() => {
    const node = frame.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(entry.contentRect.width);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const labelled = series.length > 1;
  const right = labelled ? 86 : 14;
  const plotWidth = Math.max(80, width - MARGIN.left - right);
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;

  const xs = series[0]?.values.map(([x]) => x) ?? [];
  const xMin = xs[0] ?? 0;
  const xMax = xs[xs.length - 1] ?? 1;
  const scaleX = (x: number) => MARGIN.left + ((x - xMin) / (xMax - xMin || 1)) * plotWidth;
  const scaleY = (y: number) =>
    MARGIN.top + (1 - (y - yDomain[0]) / (yDomain[1] - yDomain[0])) * plotHeight;

  const yTicks = useMemo(
    () => Array.from({ length: 5 }, (_, i) => yDomain[0] + ((yDomain[1] - yDomain[0]) * i) / 4),
    [yDomain],
  );
  const xTicks = useMemo(
    () => Array.from({ length: 4 }, (_, i) => xMin + ((xMax - xMin) * i) / 3),
    [xMin, xMax],
  );

  // Direct labels at the line ends, nudged apart so that they never overlap.
  const endLabels = useMemo(() => {
    if (!labelled) return [];
    const placed = series
      .map((s) => {
        const last = s.values[s.values.length - 1]!;
        return { key: s.key, label: s.label, y: scaleY(last[1]) };
      })
      .sort((a, b) => a.y - b.y);
    for (let i = 1; i < placed.length; i++) {
      placed[i]!.y = Math.max(placed[i]!.y, placed[i - 1]!.y + 14);
    }
    return placed;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, plotHeight, yDomain, labelled]);

  const nearest = (clientX: number, rect: DOMRect) => {
    const x = clientX - rect.left;
    let best = 0;
    xs.forEach((value, i) => {
      if (Math.abs(scaleX(value) - x) < Math.abs(scaleX(xs[best]!) - x)) best = i;
    });
    return best;
  };

  const tooltipLeft = cursor === null ? 0 : scaleX(xs[cursor]!);
  const flip = tooltipLeft > width / 2;

  return (
    <figure className="space-y-2">
      <figcaption className="text-[14px] font-medium">{title}</figcaption>
      {labelled && (
        <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[13px] text-ink-2">
          {series.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="h-0.5 w-3.5 rounded-full" style={{ background: s.color }} />
              {s.label}
            </li>
          ))}
        </ul>
      )}
      <div ref={frame} className="relative">
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={`${title}. ${yLabel} against ${xLabel}. Use the left and right arrow keys to read values.`}
          tabIndex={0}
          className="block touch-pan-y"
          onPointerMove={(e) => setCursor(nearest(e.clientX, e.currentTarget.getBoundingClientRect()))}
          onPointerLeave={() => setCursor(null)}
          onBlur={() => setCursor(null)}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") setCursor((c) => Math.min((c ?? -1) + 1, xs.length - 1));
            if (e.key === "ArrowLeft") setCursor((c) => Math.max((c ?? 1) - 1, 0));
          }}
        >
          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={MARGIN.left + plotWidth}
                y1={scaleY(tick)}
                y2={scaleY(tick)}
                stroke="var(--color-line)"
              />
              <text
                x={MARGIN.left - 6}
                y={scaleY(tick) + 4}
                textAnchor="end"
                className="fill-ink-3 font-mono text-[11px]"
              >
                {formatTick(tick)}
              </text>
            </g>
          ))}
          {xTicks.map((tick) => (
            <text
              key={tick}
              x={scaleX(tick)}
              y={HEIGHT - MARGIN.bottom + 15}
              textAnchor="middle"
              className="fill-ink-3 font-mono text-[11px]"
            >
              {formatX(tick)}
            </text>
          ))}
          <text
            x={MARGIN.left + plotWidth / 2}
            y={HEIGHT - 4}
            textAnchor="middle"
            className="fill-ink-3 text-[12px]"
          >
            {xLabel}
          </text>
          {baseline !== undefined && (
            <line
              x1={MARGIN.left}
              x2={MARGIN.left + plotWidth}
              y1={scaleY(baseline)}
              y2={scaleY(baseline)}
              stroke="var(--color-ink-3)"
              strokeDasharray="3 3"
            />
          )}
          {markers.map((marker, i) => (
            <g key={marker.label}>
              <line
                x1={scaleX(marker.x)}
                x2={scaleX(marker.x)}
                y1={MARGIN.top}
                y2={MARGIN.top + plotHeight}
                stroke="var(--color-ink-2)"
                strokeDasharray="4 3"
              />
              <text
                x={scaleX(marker.x) - 5}
                y={MARGIN.top + 11 + i * 15}
                textAnchor="end"
                className="fill-ink-2 text-[12px]"
              >
                {marker.label}
              </text>
            </g>
          ))}
          {series.map((s) => (
            <polyline
              key={s.key}
              fill="none"
              stroke={s.color}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              points={s.values.map(([x, y]) => `${scaleX(x)},${scaleY(y)}`).join(" ")}
            />
          ))}
          {endLabels.map((label) => (
            <text
              key={label.key}
              x={MARGIN.left + plotWidth + 6}
              y={label.y + 4}
              className="fill-ink-2 text-[12px]"
            >
              {label.label}
            </text>
          ))}
          {cursor !== null && (
            <g>
              <line
                x1={scaleX(xs[cursor]!)}
                x2={scaleX(xs[cursor]!)}
                y1={MARGIN.top}
                y2={MARGIN.top + plotHeight}
                stroke="var(--color-ink)"
              />
              {series.map((s) => (
                <circle
                  key={s.key}
                  cx={scaleX(xs[cursor]!)}
                  cy={scaleY(s.values[cursor]![1])}
                  r={4}
                  fill={s.color}
                  stroke="var(--color-surface)"
                  strokeWidth={2}
                />
              ))}
            </g>
          )}
        </svg>
        {cursor !== null && (
          <div
            className="pointer-events-none absolute top-2 z-10 rounded-md border border-line bg-surface px-2.5 py-1.5 text-[13px] shadow-md"
            style={flip ? { right: width - tooltipLeft + 10 } : { left: tooltipLeft + 10 }}
          >
            <div className="text-ink-3">
              {xLabel}: {formatX(xs[cursor]!)}
            </div>
            {series.map((s) => (
              <div key={s.key} className="flex items-center gap-2 whitespace-nowrap">
                <span className="h-0.5 w-3 rounded-full" style={{ background: s.color }} />
                <span className="font-mono font-medium">{formatY(s.values[cursor]![1])}</span>
                <span className="text-ink-3">{s.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <button
        type="button"
        className="text-[13px] text-ink-2 underline underline-offset-2 hover:text-ink"
        aria-expanded={showTable}
        onClick={() => setShowTable((v) => !v)}
      >
        {showTable ? "Hide table" : "Show as table"}
      </button>
      {showTable && (
        <div className="max-h-52 overflow-y-auto">
          <Table
            head={[xLabel, ...series.map((s) => s.label)]}
            rows={xs
              .filter((_, i) => xs.length <= 40 || i % Math.ceil(xs.length / 25) === 0)
              .map((x) => [
                formatX(x),
                ...series.map((s) => formatY(s.values[xs.indexOf(x)]![1])),
              ])}
          />
        </div>
      )}
    </figure>
  );
}
