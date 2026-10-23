import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { api } from "../../api/client";
import type { Run, RunDetail } from "../../api/types";
import {
  makeDetail,
  makeFailedDetail,
  makeFailedRun,
  makeReviewsById,
  makeRun,
  makeSummary,
} from "../../test/factories";
import { renderWithProviders, stubApi } from "../../test/render";
import { RunDetailPage } from "./RunDetailPage";

afterEach(() => vi.restoreAllMocks());

const ROWS = Object.values(makeReviewsById());

function show(run: Run, detail: RunDetail = makeDetail(run), route = `/runs/${run.run_id}`) {
  stubApi({
    runs: [makeSummary(run)],
    details: { [run.run_id]: detail },
    rows: ROWS,
  });
  return renderWithProviders(
    <Routes>
      <Route path="/runs/:runId" element={<RunDetailPage />} />
    </Routes>,
    { route },
  );
}

async function ready(run: Run = makeRun()) {
  await screen.findByRole("heading", { name: "Pipeline timeline" });
  return run;
}

describe("pipeline timeline", () => {
  it("shows each stage with its duration, and the stages that did not run", async () => {
    show(makeRun());
    await ready();
    const ingest = screen.getByRole("listitem", { name: /^Ingest/ });
    expect(ingest).toHaveTextContent("79.7s");
    expect(ingest).toHaveTextContent("52");
    expect(screen.getByRole("listitem", { name: /^Publish to Doc/ })).toHaveTextContent("Not run");
    expect(screen.getByRole("listitem", { name: /^Create draft/ })).toHaveTextContent("Not run");
  });

  it("names the slowest stage and the total time", async () => {
    show(makeRun());
    await ready();
    expect(screen.getByText("Slowest: Theme (77.1% of 7m 16s)")).toBeInTheDocument();
    expect(screen.getByText("Total time: 7m 16s")).toBeInTheDocument();
  });

  it("keeps stage notes but never prints a filesystem path", async () => {
    const run = makeRun();
    // Built from parts so this file itself holds no path into the review cache.
    const cachePath = ["data", "raw", "20261022-121514", "reviews.json"].join("\\");
    run.stages[0].notes = [`raw cache: ${cachePath}`];
    show(run);
    await ready();
    expect(document.body).not.toHaveTextContent(/raw cache/i);
    expect(screen.getByText("analysing a sample of 500 of 3029 reviews")).toBeInTheDocument();
  });

  it("shows the failed Theme stage and the violation for a failed run", async () => {
    const run = makeFailedRun();
    show(run, makeFailedDetail(run));
    await ready();
    const theme = screen.getByRole("listitem", { name: /^Theme/ });
    expect(theme).toHaveTextContent("Failed");
    expect(screen.getByRole("listitem", { name: /^Rank/ })).toHaveTextContent("Not run");
    expect(screen.getByRole("alert")).toHaveTextContent(/Groq tokens-per-day limit reached/);
  });
});

describe("theme table", () => {
  it("lists all six themes including Other, with Other excluded", async () => {
    show(makeRun());
    const table = await screen.findByRole("table", { name: "All themes" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(6);
    expect(rows[0]).toHaveTextContent("Other");
    expect(rows[0]).toHaveTextContent("0.493");
    expect(rows[0]).toHaveTextContent("Excluded: catch-all");
    expect(within(rows[0]).getAllByRole("cell")[0]).toHaveTextContent("1");
  });

  it("marks the three top themes, in score order", async () => {
    show(makeRun());
    const table = await screen.findByRole("table", { name: "All themes" });
    const rows = within(table).getAllByRole("row").slice(1);
    const selected = rows.filter((r) => /Selected \(Top 3\)/.test(r.textContent ?? ""));
    expect(selected.map((r) => within(r).getAllByRole("cell")[1].textContent)).toEqual([
      "Customer Support",
      "Trading Experience and App Performance",
      "Payments and Withdrawals",
    ]);
    expect(rows.filter((r) => /Not selected/.test(r.textContent ?? ""))).toHaveLength(2);
  });

  it("explains Other, with its share of the sample", async () => {
    show(makeRun());
    expect(
      await screen.findByText(
        "Other is a catch-all and is never one of the top 3, even when it scores highest (here it is 60.4% of the sample).",
      ),
    ).toBeInTheDocument();
  });

  it("is absent when the run has no ranking", async () => {
    const run = makeFailedRun();
    show(run, makeFailedDetail(run));
    await ready();
    expect(screen.queryByRole("table", { name: "All themes" })).not.toBeInTheDocument();
    expect(screen.getByText(/theme scores unavailable/i)).toBeInTheDocument();
  });
});

describe("LLM usage", () => {
  it("shows calls, tokens, waits and the configured models", async () => {
    show(makeRun());
    const section = await screen.findByRole("region", { name: "LLM usage" });
    const theme = within(section).getByRole("row", { name: /theme_assign/ });
    expect(theme).toHaveTextContent("13");
    expect(theme).toHaveTextContent("15");
    expect(theme).toHaveTextContent("286");
    expect(theme).toHaveTextContent("openai/gpt-oss-20b");
    expect(within(section).getByRole("row", { name: /compose/ })).toHaveTextContent("openai/gpt-oss-120b");
    expect(section).toHaveTextContent("53,771");
    expect(section).toHaveTextContent("Configured now (not recorded per run)");
    expect(section).toHaveTextContent("theme_assign@1");
    expect(section).not.toHaveTextContent(/cost|\$/i);
  });
});

describe("violations", () => {
  it("lists them verbatim as errors for a failed run", async () => {
    const run = makeFailedRun();
    show(run, makeFailedDetail(run));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(run.violations[0]);
  });

  it("shows guardrail messages on a completed run as warnings, not errors", async () => {
    show(makeRun({ violations: ["[word_limit] close to the limit"] }));
    const region = await screen.findByRole("region", { name: "Violations" });
    expect(region).toHaveTextContent("[word_limit] close to the limit");
    expect(within(region).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("says there were none", async () => {
    show(makeRun());
    expect(await screen.findByText("No violations recorded")).toBeInTheDocument();
  });
});

describe("review explorer", () => {
  it("shows the first page with the total", async () => {
    show(makeRun());
    const explorer = await screen.findByRole("region", { name: "Analysed reviews" });
    await within(explorer).findByText("150 reviews");
    expect(within(explorer).getAllByRole("row").length).toBe(26); // header + 25
  });

  it("asks the API for rating=1 and shows the filtered total", async () => {
    show(makeRun());
    const explorer = await screen.findByRole("region", { name: "Analysed reviews" });
    await within(explorer).findByText("150 reviews");
    const spy = vi.mocked(api.getReviews);
    await userEvent.selectOptions(within(explorer).getByLabelText("Rating"), "1");
    const ones = ROWS.filter((r) => r.rating === 1).length;
    await within(explorer).findByText(`${ones} reviews`);
    expect(spy.mock.calls.some(([, p]) => p?.rating?.length === 1 && p.rating[0] === 1)).toBe(true);
  });

  it("filters by theme", async () => {
    show(makeRun());
    const explorer = await screen.findByRole("region", { name: "Analysed reviews" });
    await within(explorer).findByText("150 reviews");
    await userEvent.selectOptions(within(explorer).getByLabelText("Theme"), "customer-support");
    const n = ROWS.filter((r) => r.theme_id === "customer-support").length;
    await within(explorer).findByText(`${n} reviews`);
  });

  it("debounces text search by 250 ms", async () => {
    show(makeRun());
    const explorer = await screen.findByRole("region", { name: "Analysed reviews" });
    await within(explorer).findByText("150 reviews");
    const spy = vi.mocked(api.getReviews);
    spy.mockClear();
    await userEvent.type(within(explorer).getByLabelText("Search text"), "app");
    expect(spy.mock.calls.some(([, p]) => p?.q)).toBe(false);
    await waitFor(() => expect(spy.mock.calls.some(([, p]) => p?.q === "app")).toBe(true));
    expect(spy.mock.calls.filter(([, p]) => p?.q).length).toBe(1);
  });

  it("pages 25 at a time", async () => {
    show(makeRun());
    const explorer = await screen.findByRole("region", { name: "Analysed reviews" });
    await within(explorer).findByText("150 reviews");
    expect(within(explorer).getByText("Page 1 of 6")).toBeInTheDocument();
    await userEvent.click(within(explorer).getByRole("button", { name: "Next page" }));
    expect(await within(explorer).findByText("Page 2 of 6")).toBeInTheDocument();
  });

  it("jumps from a top quote to that review", async () => {
    show(makeRun());
    const explorer = await screen.findByRole("region", { name: "Analysed reviews" });
    await within(explorer).findByText("150 reviews");
    const links = within(explorer).getAllByRole("button", { name: /show in explorer/i });
    expect(links).toHaveLength(3);
    await userEvent.click(links[0]);
    expect(await within(explorer).findByText("1 review")).toBeInTheDocument();
    expect(within(explorer).getByText(/showing one review by id/i)).toBeInTheDocument();
    await userEvent.click(within(explorer).getByRole("button", { name: /clear/i }));
    await within(explorer).findByText("150 reviews");
  });

  it("has three charts about the analysed sample, each with a table view", async () => {
    show(makeRun());
    const explorer = await screen.findByRole("region", { name: "Analysed reviews" });
    await within(explorer).findByText("150 reviews");
    const figures = within(explorer).getAllByRole("figure");
    expect(figures).toHaveLength(3);
    for (const figure of figures) {
      expect(figure).toHaveAccessibleName(/analysed sample \(150 reviews\)$/);
      await userEvent.click(within(figure).getByRole("button", { name: "View as table" }));
      expect(within(figure).getByRole("table")).toBeInTheDocument();
    }
  });

  it("has no export or device columns", async () => {
    show(makeRun());
    const explorer = await screen.findByRole("region", { name: "Analysed reviews" });
    await within(explorer).findByText("150 reviews");
    expect(explorer).not.toHaveTextContent(/export|device|android|ios/i);
  });

  it("says when there are no reviews", async () => {
    stubApi({ runs: [makeSummary(makeRun())], details: { "20261022-121514": makeDetail() }, rows: [] });
    renderWithProviders(
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>,
      { route: "/runs/20261022-121514" },
    );
    expect(await screen.findByText("No reviews match")).toBeInTheDocument();
  });
});

describe("page", () => {
  it("resolves /runs/latest to the newest run", async () => {
    const run = makeRun();
    show(run, makeDetail(run), "/runs/latest");
    expect(await screen.findByRole("heading", { name: "Pipeline timeline" })).toBeInTheDocument();
    expect(screen.getByText("20261022-121514")).toBeInTheDocument();
  });

  it("shows not found for an unknown run", async () => {
    stubApi({ runs: [], details: {} });
    renderWithProviders(
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>,
      { route: "/runs/20990101-000000" },
    );
    expect(await screen.findByText(/run details unavailable/i)).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = show(makeRun());
    const explorer = await screen.findByRole("region", { name: "Analysed reviews" });
    await within(explorer).findByText("150 reviews");
    expect(await axe(container)).toHaveNoViolations();
  });
});
