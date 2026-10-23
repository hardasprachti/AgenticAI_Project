import type {
  ActiveRun,
  ConfigView,
  LedgerView,
  ReviewPage,
  ReviewParams,
  ReviewSummary,
  RunDetail,
  RunSummary,
  StartRunBody,
  StartRunResponse,
} from "./types";

/** Every endpoint the dashboard uses. The HTTP client and the mock both implement this. */
export interface Api {
  listRuns(): Promise<RunSummary[]>;
  getRun(runId: string): Promise<RunDetail>;
  getReviews(runId: string, params?: ReviewParams): Promise<ReviewPage>;
  getReviewsSummary(runId: string): Promise<ReviewSummary>;
  getLedger(): Promise<LedgerView>;
  getConfig(): Promise<ConfigView>;
  startRun(body: StartRunBody): Promise<StartRunResponse>;
  getActive(): Promise<ActiveRun>;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Read per call so tests can flip it with `vi.stubEnv`. */
export function isMockMode(): boolean {
  return import.meta.env.VITE_MOCK === "1";
}

export function reviewQuery(params: ReviewParams = {}): string {
  const search = new URLSearchParams();
  for (const theme of params.theme ?? []) search.append("theme", theme);
  for (const rating of params.rating ?? []) search.append("rating", String(rating));
  for (const id of params.review_id ?? []) search.append("review_id", id);
  if (params.q) search.set("q", params.q);
  if (params.page) search.set("page", String(params.page));
  if (params.page_size) search.set("page_size", String(params.page_size));
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  } catch {
    /* not JSON */
  }
  return response.statusText || `Request failed (${response.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Cannot reach the API. Is it running on 127.0.0.1:8000?");
  }
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
  return (await response.json()) as T;
}

const runPath = (runId: string) => `/api/runs/${encodeURIComponent(runId)}`;

const httpApi: Api = {
  listRuns: () => request("/api/runs"),
  getRun: (runId) => request(runPath(runId)),
  getReviews: (runId, params) => request(`${runPath(runId)}/reviews${reviewQuery(params)}`),
  getReviewsSummary: (runId) => request(`${runPath(runId)}/reviews/summary`),
  getLedger: () => request("/api/ledger"),
  getConfig: () => request("/api/config"),
  startRun: (body) =>
    request("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getActive: () => request("/api/runs/active"),
};

/** Loads the mock (and its fixtures) on first use, so the production bundle never carries them. */
function lazyMockApi(): Api {
  const load = () => import("./mock").then((m) => m.mockApi);
  return {
    listRuns: async () => (await load()).listRuns(),
    getRun: async (runId) => (await load()).getRun(runId),
    getReviews: async (runId, params) => (await load()).getReviews(runId, params),
    getReviewsSummary: async (runId) => (await load()).getReviewsSummary(runId),
    getLedger: async () => (await load()).getLedger(),
    getConfig: async () => (await load()).getConfig(),
    startRun: async (body) => (await load()).startRun(body),
    getActive: async () => (await load()).getActive(),
  };
}

export const api: Api = isMockMode() ? lazyMockApi() : httpApi;
