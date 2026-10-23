import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { ReviewRow } from "../../api/types";
import {
  makeConfig,
  makeDetail,
  makeFailedRun,
  makePartialRun,
  makePulse,
  makeReviewsById,
  makeRun,
} from "../../test/factories";
import { renderWithProviders, stubApi } from "../../test/render";
import { GuardrailChecklist } from "./GuardrailChecklist";
import { PublishedNote } from "./PublishedNote";
import { PublishingStatus } from "./PublishingStatus";

afterEach(() => vi.restoreAllMocks());

const NOTE = makeDetail().note as string;
const DOC = "https://docs.google.com/document/d/EXAMPLE_DOCUMENT_ID/edit";

describe("PublishedNote", () => {
  it("renders note.txt verbatim in a pre-wrapped mono block", () => {
    renderWithProviders(<PublishedNote note={NOTE} wordCount={192} maxWords={250} dryRun={false} />);
    const block = screen.getByTestId("note-text");
    expect(block.textContent).toBe(NOTE);
    expect(block.className).toContain("whitespace-pre-wrap");
    expect(block.className).toContain("font-data-code");
  });

  it("shows the word gauge from the config limit", () => {
    renderWithProviders(<PublishedNote note={NOTE} wordCount={192} maxWords={250} dryRun={false} />);
    expect(screen.getByText("192 / 250 words")).toBeInTheDocument();
    const meter = screen.getByRole("meter", { name: "Word count" });
    expect(meter).toHaveAttribute("aria-valuenow", "192");
    expect(meter).toHaveAttribute("aria-valuemax", "250");
  });

  it("labels what was published, or what would be for a dry run", () => {
    const { unmount } = renderWithProviders(
      <PublishedNote note={NOTE} wordCount={192} maxWords={250} dryRun={false} />,
    );
    expect(screen.getByText("What was published")).toBeInTheDocument();
    unmount();
    renderWithProviders(<PublishedNote note={NOTE} wordCount={192} maxWords={250} dryRun />);
    expect(screen.getByText("What would be published (dry run)")).toBeInTheDocument();
  });

  it("copies exactly note.txt, hyphens and all", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderWithProviders(<PublishedNote note={NOTE} wordCount={192} maxWords={250} dryRun />);
    await userEvent.click(screen.getByRole("button", { name: /copy note/i }));
    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText.mock.calls[0][0]).toBe(NOTE);
    expect(NOTE).toContain("Groww Weekly Review Pulse - 2026-W43");
  });

  it("flags a note over the limit", () => {
    renderWithProviders(<PublishedNote note={NOTE} wordCount={260} maxWords={250} dryRun />);
    expect(screen.getByText("260 / 250 words")).toBeInTheDocument();
    expect(screen.getByText(/over the limit/i)).toBeInTheDocument();
  });

  it("is DataUnavailable without a note", () => {
    renderWithProviders(<PublishedNote note={null} wordCount={0} maxWords={250} dryRun />);
    expect(screen.getByText(/published note unavailable/i)).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(
      <PublishedNote note={NOTE} wordCount={192} maxWords={250} dryRun />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("PublishingStatus", () => {
  const config = makeConfig({ draft_to: "product-leads@example.com" });

  it("says a dry run published nothing, with no link", () => {
    renderWithProviders(<PublishingStatus run={makeRun()} config={config} />);
    expect(screen.getAllByText("Not published (dry run)")).toHaveLength(2);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows Doc and draft details for a published run, and that it was never sent", () => {
    const run = makeRun({
      doc_url: DOC,
      doc_id: "EXAMPLE_DOCUMENT_ID",
      doc_revision_id: "rev_sample_43",
      draft_id: "draft_sample_43",
    });
    run.stages.push({
      name: "publish_doc",
      duration_s: 2,
      counts: { characters_appended: 1184 },
      notes: [],
    });
    renderWithProviders(<PublishingStatus run={run} config={config} />);
    expect(screen.getByRole("link", { name: /google doc/i })).toHaveAttribute("href", DOC);
    expect(screen.getByText("Section appended: Yes")).toBeInTheDocument();
    expect(document.body).toHaveTextContent("rev_sample_43");
    expect(document.body).toHaveTextContent("1,184 characters");
    expect(document.body).toHaveTextContent("draft_sample_43");
    expect(document.body).toHaveTextContent("product-leads@example.com");
    expect(document.body).toHaveTextContent("Groww Weekly Review Pulse - 2026-W43");
    expect(screen.getByText("Draft only - never sent")).toBeInTheDocument();
  });

  it("for a partial run: Doc done, draft failed, and the resume command", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const run = makePartialRun();
    renderWithProviders(<PublishingStatus run={run} config={config} />);
    expect(screen.getByRole("link", { name: /google doc/i })).toHaveAttribute("href", DOC);
    expect(screen.getByText("Section appended: Yes")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    const command = `python -m pulse run --resume ${run.run_id}`;
    expect(screen.getByText(command)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /copy command/i }));
    expect(writeText).toHaveBeenCalledWith(command);
    expect(screen.getAllByRole("button")).toHaveLength(1); // the copy button, nothing that runs
  });

  it("says nothing was published for a failed run", () => {
    renderWithProviders(<PublishingStatus run={makeFailedRun()} config={config} />);
    expect(screen.getByText("Nothing published")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<PublishingStatus run={makeRun()} config={config} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("GuardrailChecklist", () => {
  const config = makeConfig();
  const RUN_ID = "20261022-121514";

  function stubReviews(alter?: (rows: Record<string, ReviewRow>) => void) {
    const rows = makeReviewsById();
    alter?.(rows);
    stubApi({
      reviews: (_id, params) => {
        const items = (params?.review_id ?? []).map((id) => rows[id]).filter(Boolean);
        return { items, total: items.length, page: 1, page_size: 100 };
      },
    });
  }

  function renderList(props: { pulse?: ReturnType<typeof makePulse> | null } = {}) {
    return renderWithProviders(
      <GuardrailChecklist
        runId={RUN_ID}
        run={makeRun()}
        pulse={"pulse" in props ? (props.pulse ?? null) : makePulse()}
        config={config}
      />,
    );
  }

  it("passes 7 / 7 for the real run", async () => {
    stubReviews();
    renderList();
    expect(await screen.findByText("7 / 7 passed")).toBeInTheDocument();
  });

  it("is 6 / 7 when a quote's text no longer matches, and the failing row names the quote", async () => {
    const quoteId = makePulse().quotes[1].review_id;
    stubReviews((rows) => {
      rows[quoteId] = { ...rows[quoteId], text: "Something completely different" };
    });
    renderList();
    expect(await screen.findByText("6 / 7 passed")).toBeInTheDocument();
    const row = screen.getByRole("listitem", { name: /verbatim quotes/i });
    expect(row).toHaveTextContent("Fail");
    expect(row).toHaveTextContent("2602b3…4880396");
    expect(row).toHaveTextContent(/not verbatim/);
  });

  it("lists the five redaction counts and says raw reviews are never shown", async () => {
    stubReviews();
    renderList();
    await screen.findByText("7 / 7 passed");
    const row = screen.getByRole("listitem", { name: /no reviewer identity/i });
    for (const n of ["34", "3", "2"]) expect(row).toHaveTextContent(n);
    expect(within(row).getAllByRole("listitem")).toHaveLength(5);
    expect(row).toHaveTextContent("Raw reviews are never shown here");
  });

  it("marks pulse-dependent rows Unavailable and does not count them", async () => {
    stubReviews();
    renderList({ pulse: null });
    const header = await screen.findByText(/ \/ 7 passed/);
    expect(header).toHaveTextContent(/^[0-2] \/ 7 passed$/);
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThanOrEqual(5);
  });

  it("gives pass, fail and unavailable different icons as well as words", async () => {
    stubReviews((rows) => {
      const id = makePulse().quotes[0].review_id;
      rows[id] = { ...rows[id], text: "nope" };
    });
    renderWithProviders(
      <GuardrailChecklist runId={RUN_ID} run={makeRun({ theme_scores: {} })} pulse={makePulse()} config={config} />,
    );
    await screen.findByText(/ \/ 7 passed/);
    const status = (re: RegExp) => screen.getByRole("listitem", { name: re }).querySelector("svg");
    const icons = new Set([
      status(/verbatim quotes/i)?.getAttribute("data-status-icon"),
      status(/no reviewer identity/i)?.getAttribute("data-status-icon"),
      status(/clustering themes/i)?.getAttribute("data-status-icon"),
    ]);
    expect(icons.size).toBe(3);
  });

  it("has no axe violations", async () => {
    stubReviews();
    const { container } = renderList();
    await screen.findByText("7 / 7 passed");
    expect(await axe(container)).toHaveNoViolations();
  });
});
