import { describe, expect, it } from "vitest";
import {
  makeAlreadyPublishedRun,
  makeFailedRun,
  makePartialRun,
  makeRun,
} from "../test/factories";
import { formatDuration } from "./format";
import { slowestStage, STAGE_ORDER, stageRows, totalDuration } from "./stages";

describe("stageRows", () => {
  it("lists the eight known stages in order", () => {
    expect(STAGE_ORDER).toEqual([
      "ingest",
      "sanitize",
      "theme",
      "rank",
      "compose",
      "render",
      "publish_doc",
      "publish_draft",
    ]);
  });

  it("marks the two publish stages of a dry run as not run", () => {
    const rows = stageRows(makeRun());
    expect(rows).toHaveLength(8);
    expect(rows.slice(0, 6).every((r) => r.state === "done")).toBe(true);
    expect(rows.slice(6).map((r) => [r.name, r.state, r.duration_s])).toEqual([
      ["publish_doc", "not_run", null],
      ["publish_draft", "not_run", null],
    ]);
  });

  it("carries counts and notes of a recorded stage", () => {
    const sanitize = stageRows(makeRun())[1];
    expect(sanitize.counts.clean).toBe(3029);
    expect(sanitize.notes).toEqual(["analysing a sample of 500 of 3029 reviews"]);
  });

  it("marks the last recorded stage of a failed run as failed and the rest as not run", () => {
    const rows = stageRows(makeFailedRun());
    expect(rows.map((r) => r.state)).toEqual([
      "done",
      "done",
      "failed",
      "not_run",
      "not_run",
      "not_run",
      "not_run",
      "not_run",
    ]);
    expect(rows[2].counts).toEqual({});
  });

  it("marks compose failed for failed_validation", () => {
    const run = makeRun({ status: "failed_validation" });
    run.stages = run.stages.filter((s) => s.name !== "render");
    const rows = stageRows(run);
    expect(rows.find((r) => r.name === "compose")?.state).toBe("failed");
    expect(rows.find((r) => r.name === "render")?.state).toBe("not_run");
  });

  it("marks publish_draft failed for a partial run", () => {
    const rows = stageRows(makePartialRun());
    expect(rows.find((r) => r.name === "publish_doc")?.state).toBe("done");
    expect(rows.find((r) => r.name === "publish_draft")?.state).toBe("failed");
  });

  it("is all not_run for a run with no stages", () => {
    const rows = stageRows(makeAlreadyPublishedRun());
    expect(rows).toHaveLength(8);
    expect(rows.every((r) => r.state === "not_run")).toBe(true);
    expect(stageRows(makeFailedRun({ stages: [] })).every((r) => r.state === "not_run")).toBe(true);
  });

  it("ignores stage names it does not know", () => {
    const run = makeRun();
    run.stages.push({ name: "mystery", duration_s: 1, counts: {}, notes: [] });
    expect(stageRows(run)).toHaveLength(8);
  });
});

describe("slowestStage / totalDuration", () => {
  it("finds the theme stage at 77.1% of the real run", () => {
    const slowest = slowestStage(makeRun());
    expect(slowest?.name).toBe("theme");
    expect(slowest?.pct.toFixed(1)).toBe("77.1");
  });

  it("totals the stage durations", () => {
    expect(formatDuration(totalDuration(makeRun()))).toBe("7m 16s");
    expect(formatDuration(totalDuration(makeFailedRun()))).toBe("1m 12s");
  });

  it("has no slowest stage when nothing took time", () => {
    expect(slowestStage(makeRun({ stages: [] }))).toBeNull();
    expect(totalDuration(makeRun({ stages: [] }))).toBe(0);
  });
});
