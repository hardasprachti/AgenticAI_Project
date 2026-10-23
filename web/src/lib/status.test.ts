import { describe, expect, it } from "vitest";
import {
  makeAlreadyPublishedRun,
  makeFailedRun,
  makePartialRun,
  makeRun,
} from "../test/factories";
import { isDryRun, statusPresentation } from "./status";

describe("isDryRun", () => {
  it("is a completed run with no doc_url", () => {
    expect(isDryRun(makeRun())).toBe(true);
  });

  it("is false once a doc_url is set", () => {
    expect(isDryRun(makeRun({ doc_url: "https://docs.google.com/document/d/x/edit" }))).toBe(false);
  });

  it("is false for any other status", () => {
    expect(isDryRun(makeFailedRun())).toBe(false);
    expect(isDryRun(makePartialRun())).toBe(false);
    expect(isDryRun(makeAlreadyPublishedRun({ doc_url: null }))).toBe(false);
  });
});

describe("statusPresentation", () => {
  it("labels a dry run as nothing published", () => {
    expect(statusPresentation(makeRun())).toMatchObject({
      label: "Completed · Dry run, nothing published",
      token: "dryrun",
    });
  });

  it("labels a published run as completed", () => {
    expect(
      statusPresentation(makeRun({ doc_url: "https://docs.google.com/document/d/x/edit" })),
    ).toMatchObject({ label: "Completed", token: "completed" });
  });

  it("covers every status with a label, an icon and a token", () => {
    const statuses = [
      "running",
      "completed",
      "failed_validation",
      "partial",
      "failed",
      "already_published",
      "interrupted",
      "unreadable",
    ] as const;
    for (const status of statuses) {
      const p = statusPresentation({ status, doc_url: null });
      expect(p.label.length).toBeGreaterThan(0);
      expect(p.icon.length).toBeGreaterThan(0);
      expect(p.token.length).toBeGreaterThan(0);
    }
    expect(statusPresentation(makeAlreadyPublishedRun()).label).toBe("Already published");
    expect(statusPresentation(makePartialRun()).token).toBe("partial");
    expect(statusPresentation(makeFailedRun()).token).toBe("failed");
  });
});
