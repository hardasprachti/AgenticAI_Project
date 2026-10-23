import { describe, expect, it } from "vitest";
import type { LedgerView } from "../api/types";
import { makeLedger } from "../test/factories";
import { ledgerCommands, ledgerRows } from "./ledger";

describe("ledgerRows", () => {
  it("calls doc appended + draft created complete", () => {
    const [row] = ledgerRows(makeLedger());
    expect(row).toMatchObject({ week: "2026-W43", outcome: "complete", resumeRunId: null });
  });

  it("calls doc appended with no draft draft_missing and points at the run that wrote the doc", () => {
    const view: LedgerView = {
      error: null,
      weeks: {
        "2026-W40": { doc: { state: "appended", run_id: "20261001-090000" }, draft: null },
      },
    };
    expect(ledgerRows(view)[0]).toMatchObject({
      outcome: "draft_missing",
      resumeRunId: "20261001-090000",
    });
  });

  it("treats any pending step as action required", () => {
    const rows = ledgerRows(makeLedger({ pending: true }));
    expect(rows.find((r) => r.week === "2026-W39")).toMatchObject({
      outcome: "action_required",
      resumeRunId: null,
    });
    const pendingDoc: LedgerView = {
      error: null,
      weeks: { "2026-W41": { doc: { state: "pending", run_id: "r" }, draft: null } },
    };
    expect(ledgerRows(pendingDoc)[0].outcome).toBe("action_required");
  });

  it("calls a draft with no doc action required (the orchestrator never produces that)", () => {
    const view: LedgerView = {
      error: null,
      weeks: { "2026-W41": { doc: null, draft: { state: "created", run_id: "r" } } },
    };
    expect(ledgerRows(view)[0].outcome).toBe("action_required");
  });

  it("calls the week of the run in flight in_progress", () => {
    const view: LedgerView = {
      error: null,
      weeks: {
        "2026-W44": { doc: { state: "appended", run_id: "20261029-090000" }, draft: null },
      },
    };
    expect(ledgerRows(view, "20261029-090000")[0].outcome).toBe("in_progress");
  });

  it("does not list a week with neither step", () => {
    const view: LedgerView = { error: null, weeks: { "2026-W42": { doc: null, draft: null } } };
    expect(ledgerRows(view)).toEqual([]);
  });

  it("lists the newest week first", () => {
    const rows = ledgerRows(makeLedger({ pending: true }));
    expect(rows.map((r) => r.week)).toEqual(["2026-W43", "2026-W39"]);
  });

  it("returns nothing for an unreadable ledger (the page must say protection is unknown)", () => {
    expect(ledgerRows({ weeks: {}, error: "ledger_unreadable" })).toEqual([]);
  });

  it("flags week keys that are not safe to put in a shell command", () => {
    const view: LedgerView = {
      error: null,
      weeks: { "2026-W41; rm -rf /": { doc: { state: "pending", run_id: "r" }, draft: null } },
    };
    expect(ledgerRows(view)[0].commandsSafe).toBe(false);
    expect(ledgerRows(makeLedger())[0].commandsSafe).toBe(true);
  });
});

describe("ledgerCommands", () => {
  it("returns exactly the CLI commands", () => {
    expect(ledgerCommands("2026-W39", "draft")).toEqual({
      confirm: "python -m pulse ledger confirm 2026-W39 draft",
      clear: "python -m pulse ledger clear 2026-W39 draft",
    });
  });

  it("refuses a malformed week or step", () => {
    expect(() => ledgerCommands("2026-W39; echo hi", "draft")).toThrow();
    // @ts-expect-error not a ledger step
    expect(() => ledgerCommands("2026-W39", "mail")).toThrow();
  });
});
