import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "../../components/Card";
import { ChartFrame } from "../../components/ChartFrame";
import type { Funnel as FunnelData } from "../../lib/funnel";
import { formatInt, formatPercent } from "../../lib/format";

/** Emerald steps from DESIGN.md; one hue, dark to light, so order reads as "narrowing". */
const FILL = { fetched: "#00b386", clean: "#00d09c", analysed: "#a7f3d0" } as const;

function Stat({
  title,
  value,
  percent,
  percentOf,
  children,
}: {
  title: string;
  value: number | null;
  percent?: number | null;
  percentOf?: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-outline-variant p-space-md">
      <h3 className="text-label-md uppercase text-on-surface-variant">{title}</h3>
      <p className="font-data-metric text-data-metric text-on-surface">{formatInt(value)}</p>
      {percent !== undefined && (
        <p className="text-body-sm text-on-surface-variant">
          {formatPercent(percent)} {percentOf}
        </p>
      )}
      {children}
    </div>
  );
}

function FunnelBars({ funnel }: { funnel: FunnelData }) {
  const { fetched } = funnel;
  const rows: { label: string; value: number | null; color: string }[] = [
    { label: "Fetched", value: fetched, color: FILL.fetched },
    { label: "Dropped", value: funnel.dropped.total, color: "var(--color-outline-variant)" },
    { label: "Clean", value: funnel.clean, color: FILL.clean },
    { label: "Analysed", value: funnel.analysed, color: FILL.analysed },
  ];
  const summary = rows.map((r) => `${r.label} ${formatInt(r.value)}`).join(", ");
  return (
    <div role="img" aria-label={`Review funnel: ${summary}`} className="flex flex-col gap-space-xs">
      {rows.map((row) => {
        const share = fetched && row.value !== null ? row.value / fetched : null;
        return (
          <div key={row.label} className="flex items-center gap-space-sm" aria-hidden="true">
            <span className="w-20 shrink-0 text-label-md text-on-surface-variant">{row.label}</span>
            <div className="h-5 flex-1">
              {share !== null && (
                <div
                  className="h-5 rounded-r border border-primary"
                  style={{ width: `${Math.max(share * 100, 0.8)}%`, background: row.color }}
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Funnel({ funnel, minReviews }: { funnel: FunnelData; minReviews: number | null }) {
  const { checks, dropped } = funnel;
  const table = {
    columns: ["Stage", "Reviews", "Share of fetched"],
    rows: [
      ["Fetched", formatInt(funnel.fetched), funnel.fetched ? "100%" : "—"],
      ["Dropped", formatInt(dropped.total), formatPercent(funnel.pct.dropped)],
      ["Clean", formatInt(funnel.clean), formatPercent(funnel.pct.clean)],
      [
        "Analysed",
        formatInt(funnel.analysed),
        funnel.fetched && funnel.analysed !== null ? formatPercent(funnel.analysed / funnel.fetched) : "—",
      ],
    ],
  };

  const cleaningLine = (() => {
    if (checks.cleaning.expectedClean === null || funnel.fetched === null || dropped.total === null) {
      return null;
    }
    if (checks.cleaning.ok === false) {
      return `${formatInt(funnel.fetched)} − ${formatInt(dropped.total)} = ${formatInt(checks.cleaning.expectedClean)}. Expected ${formatInt(checks.cleaning.expectedClean)} clean reviews, the run recorded ${formatInt(checks.cleaning.actualClean)}`;
    }
    return `${formatInt(funnel.fetched)} − ${formatInt(dropped.total)} = ${formatInt(checks.cleaning.expectedClean)}`;
  })();

  return (
    <Card title="Review funnel" eyebrow="From fetched to analysed" className="mb-space-lg">
      {funnel.warnings.includes("fetch_stopped_early") && (
        <p className="mb-space-md inline-flex items-center gap-space-xs rounded-full border border-status-partial-border bg-status-partial-bg px-space-sm py-space-xs text-label-md text-status-partial-fg">
          <AlertTriangle size={14} aria-hidden="true" />
          Fetch stopped early, oldest reviews may be missing
        </p>
      )}

      <div className="mb-space-lg grid grid-cols-1 gap-space-md md:grid-cols-2 xl:grid-cols-4">
        <Stat title="Fetched" value={funnel.fetched}>
          <ul className="m-0 mt-space-xs list-none p-0 text-body-sm text-on-surface-variant">
            <li>{formatInt(funnel.pages)} pages</li>
            <li>{formatInt(funnel.itemsSeen)} reviews seen</li>
            <li>{formatInt(funnel.fetched)} kept</li>
            <li>{formatInt(funnel.outsideWindow)} outside the window</li>
          </ul>
        </Stat>
        <Stat title="Dropped" value={dropped.total} percent={funnel.pct.dropped} percentOf="of fetched">
          <ul className="m-0 mt-space-xs list-none p-0 text-body-sm text-on-surface-variant">
            <li>{formatInt(dropped.short)} too short</li>
            <li>{formatInt(dropped.nonEnglish)} not English</li>
            <li>{formatInt(dropped.duplicate)} duplicates</li>
            <li>{formatInt(dropped.invalid)} invalid</li>
          </ul>
        </Stat>
        <Stat title="Clean" value={funnel.clean} percent={funnel.pct.clean} percentOf="of fetched" />
        <Stat
          title="Analysed"
          value={funnel.analysed}
          percent={funnel.pct.analysedOfClean}
          percentOf="of clean"
        />
      </div>

      <ChartFrame title="Reviews at each step" table={table}>
        <FunnelBars funnel={funnel} />
      </ChartFrame>

      <div className="mt-space-md flex flex-col gap-space-xs text-body-md text-on-surface">
        {cleaningLine && (
          <p data-testid="cleaning-check" className={checks.cleaning.ok === false ? "text-status-failed-fg" : ""}>
            {checks.cleaning.ok === false && <AlertTriangle size={14} className="mr-space-xs inline" aria-hidden="true" />}
            {cleaningLine}
          </p>
        )}
        {funnel.clean !== null && minReviews !== null && funnel.marginOverMin !== null && (
          <p>
            {formatInt(funnel.clean)} clean reviews,{" "}
            {formatInt(Math.abs(funnel.marginOverMin))}{" "}
            {funnel.marginOverMin >= 0 ? "above" : "below"} the minimum of {formatInt(minReviews)}
          </p>
        )}
        {funnel.clean !== null && funnel.analysed !== null && (
          <p>
            {funnel.sampled
              ? `A fixed random sample of ${formatInt(funnel.analysed)} of ${formatInt(funnel.clean)} clean reviews was analysed.`
              : `All ${formatInt(funnel.clean)} clean reviews were analysed.`}
          </p>
        )}
      </div>
    </Card>
  );
}
