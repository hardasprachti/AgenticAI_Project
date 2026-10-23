import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { RunSummary } from "../../api/types";
import {
  makeAlreadyPublishedRun,
  makeConfig,
  makeHistory,
  makePartialRun,
  makeRun,
  makeSummary,
} from "../../test/factories";
import { renderWithProviders, stubApi } from "../../test/render";
import { RunHistoryPage } from "./RunHistoryPage";

afterEach(() => vi.restoreAllMocks());

async function show(runs: RunSummary[] = makeHistory()) {
  stubApi({ runs, config: makeConfig() });
  const view = renderWithProviders(<RunHistoryPage />);
  await screen.findByRole("table", { name: "Runs" });
  return view;
}

describe("KPI tiles", () => {
  it("computes runs, success rate and anomalies from the real mix", async () => {
    await show();
    const tiles = await screen.findByRole("region", { name: "Summary" });
    expect(within(tiles).getByText("10 runs")).toBeInTheDocument();
    expect(within(tiles).getByText("40%")).toBeInTheDocument();
    expect(within(tiles).getByText("6 failed")).toBeInTheDocument();
  });

  it("averages duration and words over completed runs, against the limit", async () => {
    await show();
    const tiles = await screen.findByRole("region", { name: "Summary" });
    expect(tiles).toHaveTextContent("7m 16s");
    expect(tiles).toHaveTextContent("192 words");
    expect(tiles).toHaveTextContent("limit 250");
  });

  it("shows the latest fetched and clean counts", async () => {
    await show();
    const tiles = await screen.findByRole("region", { name: "Summary" });
    expect(tiles).toHaveTextContent("10,366");
    expect(tiles).toHaveTextContent("3,038");
  });

  it("counts partial and validation failures separately", async () => {
    await show([
      makeSummary(makePartialRun()),
      makeSummary(makeRun({ run_id: "20261001-090000", status: "failed_validation" })),
      makeSummary(makeRun({ run_id: "20260924-090000" })),
    ]);
    const tiles = await screen.findByRole("region", { name: "Summary" });
    expect(tiles).toHaveTextContent("1 partial");
    expect(tiles).toHaveTextContent("1 failed validation");
    expect(tiles).toHaveTextContent("0 failed");
  });

  it("shows dashes rather than NaN when there are no completed runs", async () => {
    await show([makeHistory().find((r) => r.status === "failed")!]);
    const tiles = await screen.findByRole("region", { name: "Summary" });
    expect(tiles.textContent).not.toMatch(/NaN|undefined/);
    expect(tiles).toHaveTextContent("0%");
  });
});

describe("trend chart", () => {
  it("plots the four completed runs and offers a table", async () => {
    await show();
    const figure = await screen.findByRole("figure", { name: /completed runs/i });
    expect(within(figure).getByRole("img", { name: /4 completed runs/i })).toBeInTheDocument();
    await userEvent.click(within(figure).getByRole("button", { name: "View as table" }));
    const rows = within(within(figure).getByRole("table")).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(4);
    const row = rows.find((r) => /22 Oct 17:45/.test(r.textContent ?? ""));
    expect(row).toBeDefined();
    expect(row).toHaveTextContent("10,332");
    expect(row).toHaveTextContent("3,029");
    expect(row).toHaveTextContent("192");
  });

  it("has an empty state when no run completed", async () => {
    await show([makeHistory().find((r) => r.status === "failed")!]);
    expect(await screen.findByText("No completed runs yet")).toBeInTheDocument();
    expect(screen.queryByRole("figure", { name: /completed runs/i })).not.toBeInTheDocument();
  });
});

describe("runs table", () => {
  it("groups all ten rows under one week header", async () => {
    await show();
    const table = await screen.findByRole("table", { name: "Runs" });
    expect(within(table).getAllByText("2026-W43")).toHaveLength(1);
    expect(within(table).getByText("10 runs this week")).toBeInTheDocument();
    expect(within(table).getAllByRole("link", { name: "View detail" })).toHaveLength(10);
  });

  it("groups runs of different weeks separately, newest first", async () => {
    const older = makeSummary(makeRun({ run_id: "20261008-090000", week_label: "2026-W41" }));
    await show([...makeHistory(), older]);
    const table = await screen.findByRole("table", { name: "Runs" });
    expect(within(table).getByText("1 run this week")).toBeInTheDocument();
    const headers = within(table).getAllByRole("rowheader").map((h) => h.textContent);
    expect(headers.indexOf("2026-W43")).toBeLessThan(headers.indexOf("2026-W41"));
  });

  it("has status tabs with counts", async () => {
    await show();
    expect(screen.getByRole("tab", { name: "All (10)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Failed (6)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Dry run (4)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Completed (0)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Partial (0)" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Other (0)" })).toBeInTheDocument();
  });

  it("filters by tab", async () => {
    await show();
    await userEvent.click(screen.getByRole("tab", { name: "Dry run (4)" }));
    const table = screen.getByRole("table", { name: "Runs" });
    expect(within(table).getAllByRole("link", { name: "View detail" })).toHaveLength(4);
    expect(screen.getByRole("tab", { name: "Dry run (4)" })).toHaveAttribute("aria-selected", "true");
  });

  it("searches by run id", async () => {
    await show();
    await userEvent.type(screen.getByLabelText("Search run id or week"), "151338");
    const table = screen.getByRole("table", { name: "Runs" });
    expect(within(table).getAllByRole("link", { name: "View detail" })).toHaveLength(1);
    expect(table).toHaveTextContent("20261022-151338");
  });

  it("filters by week", async () => {
    const older = makeSummary(makeRun({ run_id: "20261008-090000", week_label: "2026-W41" }));
    await show([...makeHistory(), older]);
    await userEvent.selectOptions(screen.getByLabelText("Week"), "2026-W41");
    const table = screen.getByRole("table", { name: "Runs" });
    expect(within(table).getAllByRole("link", { name: "View detail" })).toHaveLength(1);
  });

  it("shows the failed run's counts, a muted analysed value and its duration", async () => {
    await show();
    const row = screen.getByRole("row", { name: /20261022-151338/ });
    expect(row).toHaveTextContent("10,366 / 3,038 / 500");
    expect(row).toHaveTextContent("1m 12s");
    const analysed = within(row).getByLabelText(/500 analysed \(sampled; model step failed\)/);
    expect(analysed.className).toContain("text-on-surface-variant");
    expect(analysed).toHaveAttribute("title", "Sampled; model step failed");
  });

  it("labels dry runs Dry run, and shows words, but no Doc link or draft id", async () => {
    await show();
    const row = screen.getByRole("row", { name: /20261022-121514/ });
    expect(within(row).getByText("Dry run")).toBeInTheDocument();
    expect(row).toHaveTextContent("192");
    expect(within(row).queryByRole("link", { name: /doc/i })).not.toBeInTheDocument();
  });

  it("links a published run's Doc and shows its draft id", async () => {
    const run = makePartialRun({ run_id: "20261001-090000", draft_id: "draft_1" });
    await show([makeSummary(run, { doc_url: "https://docs.google.com/document/d/x/edit", draft_id: "draft_1" })]);
    const row = screen.getByRole("row", { name: /20261001-090000/ });
    expect(within(row).getByRole("link", { name: /open doc/i })).toHaveAttribute(
      "href",
      "https://docs.google.com/document/d/x/edit",
    );
    expect(row).toHaveTextContent("draft_1");
  });

  it("keeps failed and interrupted rows visible", async () => {
    const interrupted = makeSummary(makeRun({ run_id: "20261023-090000", status: "interrupted", stages: [] }), {
      fetched: null,
      clean: null,
      analysed: null,
      duration_s: null,
    });
    await show([interrupted, ...makeHistory()]);
    const table = screen.getByRole("table", { name: "Runs" });
    expect(within(table).getAllByRole("link", { name: "View detail" })).toHaveLength(11);
    expect(screen.getByRole("row", { name: /20261023-090000/ })).toHaveTextContent("Interrupted");
  });

  it("gives a partial row a copyable resume command, and nothing that runs", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const partial = makeSummary(makePartialRun({ run_id: "20261001-090000" }));
    await show([partial]);
    const row = screen.getByRole("row", { name: /20261001-090000/ });
    const command = "python -m pulse run --resume 20261001-090000";
    expect(within(row).getByText(command)).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: "Copy resume command" }));
    expect(writeText).toHaveBeenCalledWith(command);
  });

  it("offers no run, resume, retry or start action anywhere", async () => {
    await show([...makeHistory(), makeSummary(makePartialRun({ run_id: "20261001-090000" }))]);
    expect(screen.queryByRole("button", { name: /^(run|resume|retry|start|publish)/i })).not.toBeInTheDocument();
  });

  it("copies a run id", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    await show();
    await userEvent.click(screen.getByRole("button", { name: "Copy 20261022-121514" }));
    expect(writeText).toHaveBeenCalledWith("20261022-121514");
  });

  it("pages 25 rows at a time", async () => {
    const many = Array.from({ length: 30 }, (_, i) =>
      makeSummary(makeRun({ run_id: `20261001-0900${String(i).padStart(2, "0")}` })),
    ).reverse();
    await show(many);
    const table = screen.getByRole("table", { name: "Runs" });
    expect(within(table).getAllByRole("link", { name: "View detail" })).toHaveLength(25);
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(within(screen.getByRole("table", { name: "Runs" })).getAllByRole("link", { name: "View detail" })).toHaveLength(5);
  });

  it("handles an already published run with no counts", async () => {
    await show([makeSummary(makeAlreadyPublishedRun({ run_id: "20261001-090000" }))]);
    const row = screen.getByRole("row", { name: /20261001-090000/ });
    expect(row.textContent).not.toMatch(/NaN|undefined|null/);
  });
});

describe("page states", () => {
  it("shows an empty state when there are no runs", async () => {
    stubApi({ runs: [] });
    renderWithProviders(<RunHistoryPage />);
    expect(await screen.findByText("No runs yet")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("says runs are unavailable when the list cannot load", async () => {
    stubApi({ runs: new Error("down") });
    renderWithProviders(<RunHistoryPage />);
    expect(await screen.findByText(/runs unavailable/i)).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = await show();
    await screen.findByRole("table", { name: "Runs" });
    expect(await axe(container)).toHaveNoViolations();
  });
});
