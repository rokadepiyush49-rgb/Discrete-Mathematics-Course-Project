import type { ReactNode } from "react";

export function Stat({
  label,
  value,
  note,
  tone,
}: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  tone?: "alert";
}) {
  return (
    <div className="min-w-0">
      <div className="text-[13px] text-ink-3">{label}</div>
      <div
        className={`font-mono text-[22px] leading-tight font-medium tabular-nums ${
          tone === "alert" ? "text-heat" : "text-ink"
        }`}
      >
        {value}
      </div>
      {note && <div className="text-[13px] text-ink-3">{note}</div>}
    </div>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-x-4 gap-y-3">{children}</div>;
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2.5 border-t border-line pt-4">
      <h3 className="text-[15px] font-semibold">{title}</h3>
      {children}
    </section>
  );
}

export function Callout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <aside className="rounded-md border-l-[3px] border-heat bg-heat-soft px-3.5 py-3">
      <div className="text-[14px] font-semibold">{title}</div>
      <div className="mt-1 text-[14px] text-ink-2">{children}</div>
    </aside>
  );
}

export function Prose({ children }: { children: ReactNode }) {
  return <p className="text-[14.5px] text-ink-2">{children}</p>;
}

export function Formula({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-md border border-line bg-paper px-3 py-2 font-mono text-[13.5px] whitespace-nowrap">
      {children}
    </div>
  );
}

export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex rounded-md bg-paper p-0.5">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={option.value === value}
          onClick={() => onChange(option.value)}
          className={`min-h-9 flex-1 rounded-[5px] px-2 text-[14px] transition-colors ${
            option.value === value
              ? "bg-surface font-medium text-ink shadow-sm"
              : "text-ink-2 hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  quiet,
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  quiet?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`min-h-9 rounded-md px-3 text-[14px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
        quiet
          ? "border border-line text-ink hover:bg-paper"
          : "bg-ink text-surface hover:bg-ink-2"
      }`}
    >
      {children}
    </button>
  );
}

export function Hint({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-line px-3 py-2.5 text-[14px] text-ink-2">
      {children}
    </div>
  );
}

export function Table({
  head,
  rows,
  align,
}: {
  head: ReactNode[];
  rows: ReactNode[][];
  align?: ("left" | "right")[];
}) {
  const side = (i: number) => (align?.[i] === "left" || (!align && i === 0) ? "text-left" : "text-right");
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13.5px]">
        <thead>
          <tr className="border-b border-line text-ink-3">
            {head.map((cell, i) => (
              <th key={i} scope="col" className={`py-1 pr-2 font-normal last:pr-0 ${side(i)}`}>
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r} className="border-b border-line/60 last:border-0">
              {row.map((cell, i) => (
                <td
                  key={i}
                  className={`py-1 pr-2 tabular-nums last:pr-0 ${side(i)} ${i ? "font-mono" : ""}`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
