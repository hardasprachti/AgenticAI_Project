import { useId } from "react";
import type { ConfigView, Pulse, RankedTheme, Ranking } from "../../api/types";
import { ChartFrame } from "../../components/ChartFrame";
import { Stars } from "../../components/Stars";
import { formatInt, formatPercent } from "../../lib/format";
import { weightedContributions, type Components } from "../../lib/themes";

const SERIES = [
  { key: "volume", label: "Volume", color: "var(--series-volume)" },
  { key: "recency", label: "Recency", color: "var(--series-recency)" },
  { key: "severity", label: "Severity", color: "var(--series-severity)" },
] as const;

/** Score bar on a fixed 0-1 scale: a short bar is a low score, not a rescaled one. */
function ScoreBar({ contributions, weights }: { contributions: Components; weights: Components }) {
  const tooltipId = useId();
  const formula = `${weights.volume} × volume + ${weights.recency} × recency + ${weights.severity} × severity`;
  return (
    <div className="group relative">
      <div
        tabIndex={0}
        role="img"
        aria-describedby={tooltipId}
        aria-label={`Score breakdown: ${SERIES.map((s) => `${s.label} ${contributions[s.key].toFixed(3)}`).join(", ")}`}
        className="flex h-3 w-full gap-[2px] overflow-hidden rounded bg-surface-container"
      >
        {SERIES.map((s) => (
          <div
            key={s.key}
            style={{ width: `${Math.max(contributions[s.key], 0) * 100}%`, background: s.color }}
            className="h-full rounded-r-[4px]"
          />
        ))}
      </div>
      <span
        role="tooltip"
        id={tooltipId}
        className="pointer-events-none absolute left-0 top-full z-10 mt-space-xs hidden whitespace-nowrap rounded-lg bg-inverse-surface px-space-sm py-space-xs text-label-md text-inverse-on-surface group-focus-within:block group-hover:block"
      >
        {formula}
      </span>
    </div>
  );
}

function ThemeCard({
  rank,
  label,
  summary,
  share,
  ranked,
  analysed,
  config,
}: {
  rank: number;
  label: string;
  summary: string;
  share: number;
  ranked: RankedTheme | undefined;
  analysed: number;
  config: ConfigView;
}) {
  const weights = config.ranking.weights;
  const contributions = ranked ? weightedContributions(ranked.components, weights) : null;
  const table = contributions && {
    columns: ["Part", "Weight", "Value", "Contribution"],
    rows: SERIES.map((s) => [
      s.label,
      String(weights[s.key]),
      ranked!.components[s.key].toFixed(3),
      contributions[s.key].toFixed(3),
    ]),
  };
  return (
    <article className="flex flex-col gap-space-sm rounded-xl border border-outline-variant bg-surface-container-lowest p-space-lg">
      <div className="flex items-start gap-space-sm">
        <span
          aria-hidden="true"
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-container text-label-md text-on-primary-container"
        >
          {rank}
        </span>
        <h3 className="font-headline-md text-headline-md">{label}</h3>
      </div>
      <p className="text-body-md text-on-surface-variant">{summary}</p>
      <p className="text-body-md">
        <span className="font-data-metric text-headline-md">{formatPercent(share)}</span> of analysed
        reviews
        {ranked && (
          <span className="text-on-surface-variant">
            {" "}
            · {formatInt(ranked.review_count)} of {formatInt(analysed)}
          </span>
        )}
      </p>
      {ranked && <Stars value={ranked.avg_rating} />}
      {ranked && contributions && table && (
        <div className="mt-space-xs">
          <ChartFrame title={`Score ${ranked.score.toFixed(3)}`} table={table}>
            <ScoreBar contributions={contributions} weights={weights} />
            <ul className="m-0 mt-space-sm flex list-none flex-wrap gap-x-space-md gap-y-space-xs p-0 text-label-md text-on-surface-variant">
              {SERIES.map((s) => (
                <li key={s.key} className="flex items-center gap-space-xs">
                  <span
                    aria-hidden="true"
                    className="h-2.5 w-2.5 rounded-sm"
                    style={{ background: s.color }}
                  />
                  {s.label} {contributions[s.key].toFixed(3)}
                </li>
              ))}
            </ul>
          </ChartFrame>
        </div>
      )}
    </article>
  );
}

export function ThemeCards({
  pulse,
  ranking,
  config,
}: {
  pulse: Pulse;
  ranking: Ranking | null;
  config: ConfigView;
}) {
  const byId = new Map((ranking?.ranked ?? []).map((r) => [r.theme.theme_id, r]));
  const themes = pulse.themes
    .map((theme) => ({ theme, ranked: byId.get(theme.theme_id) }))
    .sort((a, b) => (b.ranked?.score ?? -1) - (a.ranked?.score ?? -1));
  return (
    <section aria-labelledby="top-themes" className="mb-space-lg">
      <h2 id="top-themes" className="mb-space-md font-headline-lg text-headline-lg">
        Top themes
      </h2>
      <div className="grid grid-cols-1 gap-space-md lg:grid-cols-3">
        {themes.map(({ theme, ranked }, index) => (
          <ThemeCard
            key={theme.theme_id}
            rank={index + 1}
            label={theme.label}
            summary={theme.summary}
            share={theme.share}
            ranked={ranked}
            analysed={pulse.analysed_count}
            config={config}
          />
        ))}
      </div>
      <p className="mt-space-sm text-body-sm text-on-surface-variant">
        Shares are of the analysed sample. The published note labels this "% of reviews".
      </p>
    </section>
  );
}
