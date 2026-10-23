import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { api } from "../api/client";
import type {
  ActiveRun,
  ConfigView,
  LedgerView,
  ReviewPage,
  ReviewParams,
  ReviewRow,
  ReviewSummary,
  RunDetail,
  RunSummary,
} from "../api/types";
import { makeConfig } from "./factories";

export const IDLE: ActiveRun = {
  active: false,
  elapsed_s: null,
  last_line: null,
  started_by_api: false,
  exit_code: null,
  exit_message: null,
  new_run_id: null,
  stderr_tail: [],
};

/** The API's /reviews filtering, over an in-memory list (same rules as api/reviews.py). */
export function filterReviews(rows: ReviewRow[], params: ReviewParams = {}): ReviewPage {
  const page = params.page ?? 1;
  const size = params.page_size ?? 25;
  const needle = params.q?.toLowerCase();
  const hits = rows.filter(
    (r) =>
      (!params.theme?.length || (r.theme_id !== null && params.theme.includes(r.theme_id))) &&
      (!params.rating?.length || (r.rating !== null && params.rating.includes(r.rating))) &&
      (!params.review_id?.length || params.review_id.includes(r.review_id)) &&
      (!needle || `${r.title} ${r.text}`.toLowerCase().includes(needle)),
  );
  return { items: hits.slice((page - 1) * size, page * size), total: hits.length, page, page_size: size };
}

export function summarizeReviews(rows: ReviewRow[]): ReviewSummary {
  const rating: Record<string, number> = { "1": 0, "2": 0, "3": 0, "4": 0, "5": 0 };
  const byTheme = new Map<string | null, number[]>();
  const byWeek = new Map<string, number[]>();
  for (const r of rows) {
    if (r.rating !== null) rating[String(r.rating)] += 1;
    byTheme.set(r.theme_id, [...(byTheme.get(r.theme_id) ?? []), r.rating ?? 0]);
    const d = new Date(`${r.date}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
    const week = d.toISOString().slice(0, 10);
    byWeek.set(week, [...(byWeek.get(week) ?? []), r.rating ?? 0]);
  }
  const avg = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;
  return {
    total: rows.length,
    rating,
    weekly: [...byWeek].sort(([a], [b]) => a.localeCompare(b)).map(([week_start, xs]) => ({ week_start, count: xs.length, avg_rating: avg(xs) })),
    by_theme: [...byTheme].map(([theme_id, xs]) => ({ theme_id, count: xs.length, avg_rating: avg(xs) })),
  };
}

export interface ApiStubs {
  runs?: RunSummary[] | Error;
  details?: Record<string, RunDetail>;
  config?: ConfigView;
  reviews?: (runId: string, params: Parameters<typeof api.getReviews>[1]) => ReviewPage;
  /** Serve /reviews and /reviews/summary from this list instead of `reviews`. */
  rows?: ReviewRow[];
  summary?: ReviewSummary;
  ledger?: LedgerView;
  active?: ActiveRun;
}

/** Point the shared `api` object at canned answers. Restored by vitest's `restoreAllMocks`. */
export function stubApi(stubs: ApiStubs = {}) {
  const runs = stubs.runs ?? [];
  vi.spyOn(api, "listRuns").mockImplementation(async () => {
    if (runs instanceof Error) throw runs;
    return runs;
  });
  vi.spyOn(api, "getRun").mockImplementation(async (id) => {
    const detail = stubs.details?.[id];
    if (!detail) throw new Error(`no stub for run ${id}`);
    return detail;
  });
  vi.spyOn(api, "getConfig").mockResolvedValue(stubs.config ?? makeConfig());
  vi.spyOn(api, "getReviews").mockImplementation(async (id, params) => {
    if (stubs.rows) return filterReviews(stubs.rows, params);
    return stubs.reviews ? stubs.reviews(id, params) : { items: [], total: 0, page: 1, page_size: 25 };
  });
  vi.spyOn(api, "getReviewsSummary").mockImplementation(async () =>
    stubs.summary ?? summarizeReviews(stubs.rows ?? []),
  );
  vi.spyOn(api, "getLedger").mockResolvedValue(stubs.ledger ?? { weeks: {}, error: null });
  vi.spyOn(api, "getActive").mockResolvedValue(stubs.active ?? IDLE);
  return api;
}

export function renderWithProviders(ui: ReactElement, { route = "/" }: { route?: string } = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  });
  const wrap = (node: ReactElement) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{node}</MemoryRouter>
    </QueryClientProvider>
  );
  const view = render(wrap(ui));
  // `rerender` must keep the providers, or the new tree has no QueryClient.
  return { ...view, client, rerender: (next: ReactElement) => view.rerender(wrap(next)) };
}
