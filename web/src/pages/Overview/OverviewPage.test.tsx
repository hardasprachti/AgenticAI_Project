import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { Run } from "../../api/types";
import {
  makeAlreadyPublishedRun,
  makeDetail,
  makeFailedDetail,
  makeFailedRun,
  makePartialRun,
  makeRun,
  makeSummary,
  withStageCounts,
} from "../../test/factories";
import { renderWithProviders, stubApi } from "../../test/render";
import { OverviewPage } from "./OverviewPage";

function showRun(run: Run, detail = makeDetail(run)) {
  stubApi({ runs: [makeSummary(run)], details: { [run.run_id]: detail } });
  return renderWithProviders(<OverviewPage />);
}

afterEach(() => vi.restoreAllMocks());

describe("completed dry run (the real run)", () => {
  it("shows the funnel numbers and percentages", async () => {
    showRun(makeRun());
    expect(await screen.findByText("Review funnel")).toBeInTheDocument();
    const page = document.body;
    for (const text of [
      "10,332",
      "7,303",
      "3,029",
      "500",
      "70.7%",
      "29.3%",
      "3,009",
      "52 pages",
      "10,400",
    ]) {
      expect(page).toHaveTextContent(text);
    }
    expect(page).toHaveTextContent(
      "A fixed random sample of 500 of 3,029 clean reviews was analysed.",
    );
    expect(page).toHaveTextContent("3,029 clean reviews, 3,009 above the minimum of 20");
  });

  it("shows the three themes, quotes and actions under the funnel", async () => {
    showRun(makeRun());
    await screen.findByText("Review funnel");
    expect(await screen.findAllByRole("article")).toHaveLength(3);
    expect(screen.getByRole("heading", { name: "What users said" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Action ideas" })).toBeInTheDocument();
  });

  it("says the pulse is unavailable instead of showing nothing when its file is unreadable", async () => {
    const run = makeRun();
    showRun(run, makeDetail(run, { pulse: null, file_errors: { pulse: "unreadable" } }));
    expect(await screen.findByText(/pulse \(unreadable file\) unavailable/i)).toBeInTheDocument();
  });

  it("shows the header: week, dry-run status, run id, window, IST start, duration", async () => {
    showRun(makeRun());
    await screen.findByText("Review funnel");
    expect(screen.getByText("2026-W43")).toBeInTheDocument();
    expect(screen.getByText("Completed · Dry run, nothing published")).toBeInTheDocument();
    expect(screen.getByText("20261022-121514")).toBeInTheDocument();
    expect(screen.getByText("13 Aug - 22 Oct 2026 (10 weeks)")).toBeInTheDocument();
    expect(screen.getByText("22 Oct 2026, 17:45:14 IST")).toBeInTheDocument();
    expect(screen.getByText("7m 16s")).toBeInTheDocument();
  });

  it("keeps UTC reachable from the keyboard", async () => {
    showRun(makeRun());
    await screen.findByText("Review funnel");
    const start = screen.getByText("22 Oct 2026, 17:45:14 IST");
    expect(start).toHaveAttribute("tabindex", "0");
    expect(screen.getByText("2026-10-22 12:15:14 UTC")).toHaveAttribute("role", "tooltip");
    expect(start).toHaveAccessibleDescription("2026-10-22 12:15:14 UTC");
  });

  it("has no Open Google Doc link for a dry run, and has one once published", async () => {
    const { unmount } = showRun(makeRun());
    await screen.findByText("Review funnel");
    expect(screen.queryByRole("link", { name: /open google doc/i })).not.toBeInTheDocument();
    unmount();
    showRun(makeRun({ doc_url: "https://docs.google.com/document/d/abc/edit" }));
    const link = await screen.findByRole("link", { name: /open google doc/i });
    expect(link).toHaveAttribute("href", "https://docs.google.com/document/d/abc/edit");
  });

  it("warns when the fetch stopped early", async () => {
    showRun(withStageCounts(makeRun(), "ingest", { window_start_reached: 0 }));
    expect(
      await screen.findByText("Fetch stopped early, oldest reviews may be missing"),
    ).toBeInTheDocument();
  });

  it("does not warn on a normal fetch", async () => {
    showRun(makeRun());
    await screen.findByText("Review funnel");
    expect(screen.queryByText(/fetch stopped early/i)).not.toBeInTheDocument();
  });

  it("shows the arithmetic, and the expected-versus-actual when it does not add up", async () => {
    const { unmount } = showRun(makeRun());
    await screen.findByText("Review funnel");
    expect(screen.getByTestId("cleaning-check")).toHaveTextContent("10,332 − 7,303 = 3,029");
    unmount();
    showRun(withStageCounts(makeRun(), "sanitize", { dropped_short: 7000 }));
    const check = await screen.findByTestId("cleaning-check");
    expect(check).toHaveTextContent("Expected 3,188 clean reviews, the run recorded 3,029");
  });

  it("offers a table view of the funnel chart", async () => {
    showRun(makeRun());
    await screen.findByText("Review funnel");
    const funnel = screen.getByRole("figure", { name: "Reviews at each step" });
    await userEvent.click(within(funnel).getByRole("button", { name: "View as table" }));
    const table = within(funnel).getByRole("table");
    expect(within(table).getByRole("cell", { name: "10,332" })).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = showRun(makeRun());
    await screen.findByText("Review funnel");
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("failed run", () => {
  beforeEach(() => {
    const run = makeFailedRun();
    showRun(run, makeFailedDetail(run));
  });

  it("names the failing stage and shows the reason", async () => {
    expect(await screen.findByText("Stopped at: Theme")).toBeInTheDocument();
    expect(screen.getByText(/Groq tokens-per-day limit reached/)).toBeInTheDocument();
  });

  it("still shows the funnel up to the failure", async () => {
    await screen.findByText("Stopped at: Theme");
    expect(document.body).toHaveTextContent("10,366");
    expect(document.body).toHaveTextContent("3,038");
  });

  it("says the later sections were not produced and offers no Doc, draft or publish control", async () => {
    await screen.findByText("Stopped at: Theme");
    expect(screen.getByText(/not produced/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /google doc/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /publish/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/draft id/i)).not.toBeInTheDocument();
  });
});

describe("failed validation", () => {
  it("shows violations and retries, and that nothing was published", async () => {
    const run = makeRun({
      status: "failed_validation",
      retries: 2,
      violations: ["[word_limit] 312 words, limit is 250"],
    });
    showRun(run, makeFailedDetail(run));
    expect(await screen.findByText("[word_limit] 312 words, limit is 250")).toBeInTheDocument();
    expect(document.body).toHaveTextContent(/2 retries/);
    expect(document.body).toHaveTextContent("Nothing was published");
  });
});

describe("already published", () => {
  it("shows the panel and no funnel", async () => {
    const run = makeAlreadyPublishedRun();
    showRun(run, makeFailedDetail(run));
    expect(await screen.findByText("Already published for 2026-W43")).toBeInTheDocument();
    expect(screen.queryByText("Review funnel")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open google doc/i })).toBeInTheDocument();
    expect(document.body).toHaveTextContent("draft_sample_43");
  });
});

describe("partial run", () => {
  it("shows the resume command with a copy button for exactly that command", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const run = makePartialRun();
    showRun(run);
    const command = `python -m pulse run --resume ${run.run_id}`;
    expect((await screen.findAllByText(command)).length).toBeGreaterThan(0);
    await userEvent.click(screen.getAllByRole("button", { name: /copy command/i })[0]);
    expect(writeText).toHaveBeenCalledWith(command);
  });
});

describe("running and interrupted", () => {
  it("shows elapsed time for a running run and no numbers", async () => {
    const run = makeRun({ status: "running", stages: [] });
    showRun(run, makeFailedDetail(run));
    expect(await screen.findByText(/elapsed/i)).toBeInTheDocument();
    expect(screen.queryByText("Review funnel")).not.toBeInTheDocument();
  });

  it("explains an interrupted run", async () => {
    const run = makeRun({ status: "interrupted", stages: [] });
    showRun(run, { ...makeFailedDetail(run), run: null });
    expect(
      await screen.findByText("No run record; the process ended early"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Review funnel")).not.toBeInTheDocument();
  });
});

describe("other states", () => {
  it("shows an empty state with a dry-run button when there are no runs", async () => {
    stubApi({ runs: [] });
    renderWithProviders(<OverviewPage />);
    expect(await screen.findByRole("button", { name: "Run a dry run" })).toBeInTheDocument();
  });

  it("shows DataUnavailable for an unreadable run record", async () => {
    const run = makeRun({ status: "unreadable", stages: [] });
    showRun(run, { ...makeFailedDetail(run), run: null, file_errors: { run: "unreadable" } });
    expect(await screen.findByText(/run record unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText("Review funnel")).not.toBeInTheDocument();
  });

  it("shows DataUnavailable when the run list cannot be loaded", async () => {
    stubApi({ runs: new Error("down") });
    renderWithProviders(<OverviewPage />);
    await waitFor(() => expect(screen.getByText(/runs unavailable/i)).toBeInTheDocument());
  });
});
