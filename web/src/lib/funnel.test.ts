import { describe, expect, it } from "vitest";
import { makeFailedRun, makeRun, withStageCounts, withoutStage } from "../test/factories";
import { formatPercent } from "./format";
import { computeFunnel } from "./funnel";

describe("computeFunnel on the real completed run", () => {
  const funnel = computeFunnel(makeRun(), 20);

  it("reads the counts", () => {
    expect(funnel).toMatchObject({
      fetched: 10332,
      itemsSeen: 10400,
      outsideWindow: 68,
      pages: 52,
      dropped: { short: 7159, nonEnglish: 82, duplicate: 62, invalid: 0, total: 7303 },
      clean: 3029,
      analysed: 500,
      sampled: true,
      marginOverMin: 3009,
      reachedStage: "render",
    });
  });

  it("computes percentages as fractions", () => {
    expect(formatPercent(funnel.pct.dropped)).toBe("70.7%");
    expect(formatPercent(funnel.pct.clean)).toBe("29.3%");
    expect(formatPercent(funnel.pct.analysedOfClean)).toBe("16.5%");
  });

  it("verifies the arithmetic", () => {
    expect(funnel.checks.cleaning).toEqual({ ok: true, expectedClean: 3029, actualClean: 3029 });
    expect(funnel.checks.ingest).toEqual({ ok: true, expectedFetched: 10332, actualFetched: 10332 });
    expect(funnel.warnings).toEqual([]);
  });
});

describe("discrepancies and warnings", () => {
  it("shows a cleaning discrepancy instead of hiding it", () => {
    const run = withStageCounts(makeRun(), "sanitize", { dropped_short: 7000 });
    const { cleaning } = computeFunnel(run, 20).checks;
    // 10,332 - (7,000 + 82 + 62 + 0) = 3,188. (The plan's "3190" is an arithmetic slip.)
    expect(cleaning).toEqual({ ok: false, expectedClean: 3188, actualClean: 3029 });
  });

  it("shows an ingest discrepancy", () => {
    const run = withStageCounts(makeRun(), "ingest", { outside_window: 70 });
    expect(computeFunnel(run, 20).checks.ingest).toEqual({
      ok: false,
      expectedFetched: 10330,
      actualFetched: 10332,
    });
  });

  it("warns when the fetch was truncated", () => {
    const run = withStageCounts(makeRun(), "ingest", { truncated: 1 });
    expect(computeFunnel(run, 20).warnings).toContain("fetch_stopped_early");
  });

  it("warns when the window start was never reached", () => {
    const run = withStageCounts(makeRun(), "ingest", { window_start_reached: 0 });
    expect(computeFunnel(run, 20).warnings).toContain("fetch_stopped_early");
  });
});

describe("missing data never produces NaN or a crash", () => {
  it("the failed run's funnel goes through analysed, and stops at theme", () => {
    const funnel = computeFunnel(makeFailedRun(), 20);
    expect(funnel).toMatchObject({
      fetched: 10366,
      clean: 3038,
      analysed: 500,
      sampled: true,
      reachedStage: "theme",
    });
  });

  it("a run with no sanitize stage has null clean and analysed and null percentages", () => {
    const run = withoutStage(makeFailedRun(), "sanitize");
    const funnel = computeFunnel(run, 20);
    expect(funnel.clean).toBeNull();
    expect(funnel.analysed).toBeNull();
    expect(funnel.sampled).toBe(false);
    expect(funnel.marginOverMin).toBeNull();
    expect(funnel.dropped.total).toBeNull();
    expect(funnel.pct).toEqual({ dropped: null, clean: null, analysedOfClean: null });
    expect(funnel.checks.cleaning.ok).toBeNull();
    expect(JSON.stringify(funnel)).not.toContain("NaN");
  });

  it("a run with no stages at all is all nulls", () => {
    const funnel = computeFunnel(makeRun({ stages: [] }), 20);
    expect(funnel.fetched).toBeNull();
    expect(funnel.reachedStage).toBeNull();
    expect(funnel.warnings).toEqual([]);
    expect(funnel.checks.ingest.ok).toBeNull();
  });

  it("an empty window (fetched 0) has no percentages", () => {
    const run = withStageCounts(makeRun(), "ingest", { fetched: 0 });
    const funnel = computeFunnel(run, 20);
    expect(funnel.pct.dropped).toBeNull();
    expect(funnel.pct.clean).toBeNull();
  });

  it("no clean reviews means no analysed-of-clean percentage", () => {
    let run = withStageCounts(makeRun(), "sanitize", { clean: 0, analysed: 0 });
    run = withStageCounts(run, "sanitize", { dropped_short: 10332 - 144 });
    const funnel = computeFunnel(run, 20);
    expect(funnel.pct.analysedOfClean).toBeNull();
    expect(funnel.sampled).toBe(false);
  });
});
