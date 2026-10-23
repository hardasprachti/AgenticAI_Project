import type { ConfigView, Ranking } from "../../api/types";
import { Card } from "../../components/Card";
import { Stars } from "../../components/Stars";
import { formatInt, formatPercent } from "../../lib/format";
import { CATCH_ALL_THEME_ID, splitSelected, weightedContributions } from "../../lib/themes";

const SERIES = [
  { key: "volume", label: "volume", color: "var(--series-volume)" },
  { key: "recency", label: "recency", color: "var(--series-recency)" },
  { key: "severity", label: "severity", color: "var(--series-severity)" },
] as const;

/** All themes, best score first. Other is listed (it can rank first) but is never selected. */
export function ThemeTable({ ranking, config }: { ranking: Ranking; config: ConfigView }) {
  const { weights } = config.ranking;
  const ordered = [...ranking.ranked].sort((a, b) => b.score - a.score);
  const split = splitSelected(ordered, ranking.top);
  const selected = new Set(split.selected.map((r) => r.theme.theme_id));
  const other = ordered.find((r) => r.theme.theme_id === CATCH_ALL_THEME_ID);

  const status = (id: string) =>
    id === CATCH_ALL_THEME_ID
      ? "Excluded: catch-all"
      : selected.has(id)
        ? `Selected (Top ${ranking.top.length})`
        : "Not selected";

  return (
    <Card title="Theme ranking" eyebrow="Every theme the model found" className="mb-space-lg">
      <div className="overflow-x-auto">
        <table aria-label="All themes" className="w-full min-w-[60rem] text-left text-body-sm">
          <thead>
            <tr className="text-label-md text-on-surface-variant">
              {["Score rank", "Theme", "Reviews", "Share", "Avg rating", "Volume", "Recency", "Severity", "Score", "Status"].map((h) => (
                <th key={h} scope="col" className="border-b border-outline-variant py-space-sm pr-space-md">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ordered.map((row, index) => {
              const c = weightedContributions(row.components, weights);
              return (
                <tr key={row.theme.theme_id} className="align-middle">
                  <td className="py-space-sm pr-space-md font-data-metric">{index + 1}</td>
                  <td className="py-space-sm pr-space-md">{row.theme.label}</td>
                  <td className="py-space-sm pr-space-md">{formatInt(row.review_count)}</td>
                  <td className="py-space-sm pr-space-md">{formatPercent(row.share)}</td>
                  <td className="py-space-sm pr-space-md">
                    <Stars value={row.avg_rating} />
                  </td>
                  {SERIES.map((s) => (
                    <td key={s.key} className="py-space-sm pr-space-md">
                      <span className="flex items-center gap-space-xs">
                        <span
                          aria-hidden="true"
                          className="inline-block h-2.5 w-2.5 rounded-sm"
                          style={{ background: s.color }}
                        />
                        {row.components[s.key].toFixed(3)}
                      </span>
                    </td>
                  ))}
                  <td className="py-space-sm pr-space-md">
                    <span className="font-label-lg text-label-lg">{row.score.toFixed(3)}</span>
                    <span
                      role="img"
                      aria-label={`Weighted parts: ${SERIES.map((s) => `${s.label} ${c[s.key].toFixed(3)}`).join(", ")}`}
                      className="mt-space-xxs flex h-2 w-24 gap-[2px] overflow-hidden rounded bg-surface-container"
                    >
                      {SERIES.map((s) => (
                        <span
                          key={s.key}
                          className="block h-full rounded-r-[3px]"
                          style={{ width: `${Math.max(c[s.key], 0) * 100}%`, background: s.color }}
                        />
                      ))}
                    </span>
                  </td>
                  <td className="py-space-sm font-label-lg text-label-lg">{status(row.theme.theme_id)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-space-md text-body-sm text-on-surface-variant">
        Score = {weights.volume} × volume + {weights.recency} × recency + {weights.severity} ×
        severity, weights as configured now. The bar under each score shows those three weighted
        parts on a 0-1 scale.
      </p>
      <p className="mt-space-sm text-body-md">
        Other is a catch-all and is never one of the top {ranking.top.length}, even when it scores
        highest{other ? ` (here it is ${formatPercent(other.share)} of the sample)` : ""}.
      </p>
    </Card>
  );
}
