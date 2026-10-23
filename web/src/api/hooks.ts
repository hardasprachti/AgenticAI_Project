import { useQuery } from "@tanstack/react-query";
import { api } from "./client";
import type { ActiveRun, ReviewParams } from "./types";

export const ACTIVE_POLL_MS = 5000;

/** Poll the active-run endpoint only while a run is active; otherwise it is fetched once. */
export function activePollInterval(data: ActiveRun | undefined): number | false {
  return data?.active ? ACTIVE_POLL_MS : false;
}

export const queryKeys = {
  runs: ["runs"] as const,
  run: (runId: string) => ["run", runId] as const,
  reviews: (runId: string, params: ReviewParams) => ["reviews", runId, params] as const,
  reviewsSummary: (runId: string) => ["reviews-summary", runId] as const,
  ledger: ["ledger"] as const,
  config: ["config"] as const,
  active: ["active"] as const,
};

export function useRuns() {
  return useQuery({ queryKey: queryKeys.runs, queryFn: () => api.listRuns() });
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.run(runId ?? ""),
    queryFn: () => api.getRun(runId as string),
    enabled: Boolean(runId),
  });
}

export function useReviews(runId: string | undefined, params: ReviewParams = {}) {
  return useQuery({
    queryKey: queryKeys.reviews(runId ?? "", params),
    queryFn: () => api.getReviews(runId as string, params),
    enabled: Boolean(runId),
  });
}

export function useReviewsSummary(runId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.reviewsSummary(runId ?? ""),
    queryFn: () => api.getReviewsSummary(runId as string),
    enabled: Boolean(runId),
  });
}

export function useLedger() {
  return useQuery({ queryKey: queryKeys.ledger, queryFn: () => api.getLedger() });
}

export function useConfig() {
  return useQuery({ queryKey: queryKeys.config, queryFn: () => api.getConfig(), staleTime: 60_000 });
}

export function useActive() {
  return useQuery({
    queryKey: queryKeys.active,
    queryFn: () => api.getActive(),
    refetchInterval: (query) => activePollInterval(query.state.data),
  });
}
