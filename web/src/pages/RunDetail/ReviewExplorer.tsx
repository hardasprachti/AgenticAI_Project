import { useEffect, useState } from "react";
import { useReviews, useReviewsSummary } from "../../api/hooks";
import type { Pulse, ReviewParams } from "../../api/types";
import { Card } from "../../components/Card";
import { ChartFrame } from "../../components/ChartFrame";
import { DataUnavailable } from "../../components/DataUnavailable";
import { HBars } from "../../components/HBars";
import { Stars } from "../../components/Stars";
import { ThemeChip } from "../../components/ThemeChip";
import { formatDay, formatInt, truncateId } from "../../lib/format";
import { useDebounced } from "../../lib/useDebounced";

const PAGE_SIZE = 25;
const SEARCH_DEBOUNCE_MS = 250;

function Charts({ runId, themeLabels }: { runId: string; themeLabels: Record<string, string> }) {
  const summary = useReviewsSummary(runId);
  if (summary.isPending) return <p role="status">Loading charts…</p>;
  if (summary.isError || !summary.data) return <DataUnavailable what="Charts" />;
  const { total, rating, weekly, by_theme } = summary.data;
  const suffix = `analysed sample (${formatInt(total)} reviews)`;
  const ratingRows = [5, 4, 3, 2, 1].map((star) => ({
    label: `${star} star${star === 1 ? "" : "s"}`,
    value: rating[String(star)] ?? 0,
    text: formatInt(rating[String(star)] ?? 0),
  }));
  const themeRows = by_theme.map((t) => ({
    label: t.theme_id ? (themeLabels[t.theme_id] ?? t.theme_id) : "No theme",
    value: t.avg_rating ?? 0,
    text: t.avg_rating === null ? "—" : t.avg_rating.toFixed(1),
  }));
  const weekRows = weekly.map((w) => ({
    label: formatDay(w.week_start),
    value: w.count,
    text: formatInt(w.count),
  }));
  const maxCount = Math.max(1, ...ratingRows.map((r) => r.value));
  const maxWeek = Math.max(1, ...weekRows.map((r) => r.value));
  return (
    <div className="mb-space-lg grid grid-cols-1 gap-space-lg xl:grid-cols-3">
      <ChartFrame
        title={`Rating distribution, ${suffix}`}
        table={{ columns: ["Rating", "Reviews"], rows: ratingRows.map((r) => [r.label, r.text]) }}
      >
        <HBars rows={ratingRows} max={maxCount} label="Rating distribution" />
      </ChartFrame>
      <ChartFrame
        title={`Reviews per week, ${suffix}`}
        table={{ columns: ["Week starting", "Reviews", "Average rating"], rows: weekly.map((w) => [formatDay(w.week_start), formatInt(w.count), w.avg_rating?.toFixed(1) ?? "—"]) }}
      >
        <HBars rows={weekRows} max={maxWeek} label="Reviews per week" />
      </ChartFrame>
      <ChartFrame
        title={`Average rating per theme, ${suffix}`}
        table={{ columns: ["Theme", "Reviews", "Average rating"], rows: by_theme.map((t, i) => [themeRows[i].label, formatInt(t.count), themeRows[i].text]) }}
      >
        <HBars rows={themeRows} max={5} label="Average rating per theme" />
      </ChartFrame>
    </div>
  );
}

const SELECT =
  "rounded-lg border border-outline-variant bg-surface-container-lowest px-space-sm py-space-sm text-body-md font-normal";

/**
 * The reviews the model saw: filterable, paged, with charts over the whole sample. These are the
 * analysed reviews only (rating, date, app version, theme, title, text): no reviewer, no device.
 */
export function ReviewExplorer({
  runId,
  pulse,
  themeLabels,
}: {
  runId: string;
  pulse: Pulse | null;
  themeLabels: Record<string, string>;
}) {
  const [theme, setTheme] = useState("");
  const [rating, setRating] = useState("");
  const [search, setSearch] = useState("");
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim(), SEARCH_DEBOUNCE_MS);

  // Any change to what is being asked for starts again at page 1.
  useEffect(() => setPage(1), [theme, rating, q, reviewId]);

  const params: ReviewParams = {
    page,
    page_size: PAGE_SIZE,
    ...(theme ? { theme: [theme] } : {}),
    ...(rating ? { rating: [Number(rating)] } : {}),
    ...(q ? { q } : {}),
    ...(reviewId ? { review_id: [reviewId] } : {}),
  };
  const reviews = useReviews(runId, params);
  const total = reviews.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Card title="Analysed reviews" eyebrow="The sample the model saw" className="mb-space-lg">
      <Charts runId={runId} themeLabels={themeLabels} />

      {pulse && pulse.quotes.length > 0 && (
        <ul className="m-0 mb-space-md flex list-none flex-wrap gap-space-sm p-0">
          {pulse.quotes.map((quote) => (
            <li key={quote.review_id} className="flex items-center gap-space-xs text-body-sm">
              <span className="font-data-code text-data-code">{truncateId(quote.review_id)}</span>
              <button
                type="button"
                onClick={() => setReviewId(quote.review_id)}
                className="rounded-lg border border-outline-variant px-space-sm py-space-xs text-label-md text-primary hover:bg-surface-container-low"
              >
                Show in explorer
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mb-space-md flex flex-wrap items-end gap-space-md">
        <label className="flex flex-col gap-space-xs text-label-md">
          Theme
          <select value={theme} onChange={(e) => setTheme(e.target.value)} className={SELECT}>
            <option value="">All themes</option>
            {Object.entries(themeLabels).map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-space-xs text-label-md">
          Rating
          <select value={rating} onChange={(e) => setRating(e.target.value)} className={SELECT}>
            <option value="">Any rating</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n} star{n === 1 ? "" : "s"}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-[14rem] flex-1 flex-col gap-space-xs text-label-md">
          Search text
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={SELECT}
          />
        </label>
      </div>

      {reviewId && (
        <p className="mb-space-md flex items-center gap-space-sm text-body-md">
          Showing one review by id.
          <button
            type="button"
            onClick={() => setReviewId(null)}
            className="rounded-lg border border-outline-variant px-space-sm py-space-xs text-label-md hover:bg-surface-container-low"
          >
            Clear
          </button>
        </p>
      )}

      {reviews.isPending && <p role="status">Loading reviews…</p>}
      {reviews.isError && <DataUnavailable what="Reviews" />}
      {reviews.data && (
        <>
          <p className="mb-space-sm text-label-lg">
            {formatInt(total)} {total === 1 ? "review" : "reviews"}
          </p>
          {total === 0 ? (
            <p className="text-on-surface-variant">No reviews match</p>
          ) : (
            <div className="overflow-x-auto">
              <table aria-label="Review list" className="w-full min-w-[48rem] text-left text-body-sm">
                <thead>
                  <tr className="text-label-md text-on-surface-variant">
                    {["Rating", "Date", "App version", "Theme", "Review"].map((h) => (
                      <th key={h} scope="col" className="border-b border-outline-variant py-space-sm pr-space-md">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {reviews.data.items.map((r) => (
                    <tr key={r.review_id} className="align-top">
                      <td className="py-space-sm pr-space-md">
                        {r.rating !== null ? <Stars value={r.rating} /> : "—"}
                      </td>
                      <td className="py-space-sm pr-space-md whitespace-nowrap">{r.date ?? "—"}</td>
                      <td className="py-space-sm pr-space-md">{r.app_version ?? "—"}</td>
                      <td className="py-space-sm pr-space-md">
                        {r.theme_id ? (
                          <ThemeChip themeId={r.theme_id} label={themeLabels[r.theme_id] ?? r.theme_id} />
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="py-space-sm">
                        {r.title && <p className="font-label-lg text-label-lg">{r.title}</p>}
                        <p className="whitespace-pre-wrap">{r.text}</p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {pages > 1 && (
            <nav aria-label="Review pages" className="mt-space-md flex items-center justify-end gap-space-sm">
              <button
                type="button"
                aria-label="Previous page"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg border border-outline-variant px-space-md py-space-xs text-label-md disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-label-md">
                Page {page} of {pages}
              </span>
              <button
                type="button"
                aria-label="Next page"
                disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-outline-variant px-space-md py-space-xs text-label-md disabled:opacity-40"
              >
                Next
              </button>
            </nav>
          )}
        </>
      )}
    </Card>
  );
}
