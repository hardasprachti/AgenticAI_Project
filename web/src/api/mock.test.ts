import { afterEach, describe, expect, it, vi } from "vitest";
import { mockApi } from "./mock";

const SUCCESS = "20261022-121514";
const FAILED = "20261022-151338";

describe("mock API", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("lists the two fixture runs newest first", async () => {
    const runs = await mockApi.listRuns();
    expect(runs.map((r) => r.run_id)).toEqual([FAILED, SUCCESS]);
    const [failed, completed] = runs;
    expect(failed).toMatchObject({ status: "failed", fetched: 10366, clean: 3038, has_pulse: false });
    expect(completed).toMatchObject({
      status: "completed",
      fetched: 10332,
      clean: 3029,
      analysed: 500,
      word_count: 192,
      has_pulse: true,
      is_dry_run: true,
      doc_url: null,
    });
    expect(completed.duration_s).toBeCloseTo(435.81, 2);
  });

  it("returns the failed run without a pulse", async () => {
    const detail = await mockApi.getRun(FAILED);
    expect(detail.status).toBe("failed");
    expect(detail.pulse).toBeNull();
    expect(detail.note).toBeNull();
    expect(detail.ranking).toBeNull();
    expect(detail.run?.violations[0]).toContain("tokens-per-day");
  });

  it("returns every file of the completed run, with the note verbatim", async () => {
    const detail = await mockApi.getRun(SUCCESS);
    expect(detail.pulse?.themes).toHaveLength(3);
    expect(detail.ranking?.top[0]).toBe("customer-support");
    expect(detail.note?.startsWith("Groww Weekly Review Pulse - 2026-W43")).toBe(true);
    expect(detail.file_errors).toEqual({});
  });

  it("404s for an unknown run", async () => {
    await expect(mockApi.getRun("20990101-000000")).rejects.toMatchObject({ status: 404 });
  });

  it("filters reviews by theme", async () => {
    const page = await mockApi.getReviews(SUCCESS, { theme: ["customer-support"] });
    expect(page.total).toBeGreaterThan(0);
    expect(page.items.every((r) => r.theme_id === "customer-support")).toBe(true);
  });

  it("composes rating, text and review_id filters and paginates", async () => {
    const all = await mockApi.getReviews(SUCCESS, { page_size: 100 });
    expect(all.total).toBe(150);
    expect(all.items).toHaveLength(100);
    const second = await mockApi.getReviews(SUCCESS, { page: 2, page_size: 100 });
    expect(second.items).toHaveLength(50);

    const pick = all.items.slice(0, 3).map((r) => r.review_id);
    const byId = await mockApi.getReviews(SUCCESS, { review_id: pick });
    expect(byId.items.map((r) => r.review_id).sort()).toEqual([...pick].sort());

    const ones = await mockApi.getReviews(SUCCESS, { rating: [1] });
    expect(ones.items.every((r) => r.rating === 1)).toBe(true);

    const q = await mockApi.getReviews(SUCCESS, { q: "CUSTOMER SERVICE" });
    expect(q.items.every((r) => /customer service/i.test(`${r.title} ${r.text}`))).toBe(true);
  });

  it("gives reviews of a run with no themes file a null theme", async () => {
    const page = await mockApi.getReviews(FAILED, { page_size: 5 });
    expect(page.items.every((r) => r.theme_id === null)).toBe(true);
  });

  it("summarises the whole fixture sample", async () => {
    const s = await mockApi.getReviewsSummary(SUCCESS);
    expect(s.total).toBe(150);
    expect(Object.values(s.rating).reduce((a, b) => a + b, 0)).toBe(150);
    expect(s.by_theme.reduce((a, b) => a + b.count, 0)).toBe(150);
    expect(s.weekly.map((w) => w.week_start)).toEqual([...s.weekly.map((w) => w.week_start)].sort());
  });

  it("serves the synthetic ledger with a pending draft", async () => {
    const ledger = await mockApi.getLedger();
    expect(ledger.error).toBeNull();
    expect(ledger.weeks["2026-W39"].draft?.state).toBe("pending");
  });

  it("serves the config view", async () => {
    const config = await mockApi.getConfig();
    expect(config.ranking.weights).toEqual({ volume: 0.5, recency: 0.2, severity: 0.3 });
    expect(config.pulse.min_reviews).toBe(20);
  });

  it("refuses a real run without confirmation, like the API", async () => {
    await expect(mockApi.startRun({ source: "csv", dry_run: false })).rejects.toMatchObject({
      status: 422,
    });
  });

  it("accepts a dry run and reports no run active by default", async () => {
    expect((await mockApi.getActive()).active).toBe(false);
    const started = await mockApi.startRun({ source: "csv" });
    expect(started.pid).toBeGreaterThan(0);
  });

  it("is chosen by the client only when VITE_MOCK=1", async () => {
    vi.stubEnv("VITE_MOCK", "1");
    vi.resetModules();
    const mockMode = await import("./client");
    expect(mockMode.isMockMode()).toBe(true);
    const runs = await mockMode.api.listRuns();
    expect(runs).toHaveLength(2);

    vi.stubEnv("VITE_MOCK", "");
    vi.resetModules();
    const live = await import("./client");
    expect(live.isMockMode()).toBe(false);
  });
});
