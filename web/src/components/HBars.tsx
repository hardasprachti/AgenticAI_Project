export interface BarRow {
  label: string;
  value: number;
  /** What to print at the end of the bar (a count, an average). */
  text: string;
}

/**
 * Horizontal bars on one zero-based axis. Thin marks with a rounded data end; the number is always
 * printed, so the bar never has to be read by length or colour alone.
 */
export function HBars({ rows, max, label }: { rows: BarRow[]; max: number; label: string }) {
  return (
    <div role="img" aria-label={`${label}: ${rows.map((r) => `${r.label} ${r.text}`).join(", ")}`}>
      <div aria-hidden="true" className="flex flex-col gap-space-xs">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center gap-space-sm">
            <span className="w-28 shrink-0 truncate text-label-md text-on-surface-variant" title={row.label}>
              {row.label}
            </span>
            <div className="h-3 flex-1">
              <div
                className="h-3 rounded-r border border-primary bg-primary-container"
                style={{ width: `${max > 0 ? Math.min(Math.max(row.value / max, 0), 1) * 100 : 0}%`, minWidth: row.value > 0 ? 2 : 0 }}
              />
            </div>
            <span className="w-14 shrink-0 text-right text-label-md text-on-surface">{row.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
