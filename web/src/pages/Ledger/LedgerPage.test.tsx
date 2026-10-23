import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { LedgerView } from "../../api/types";
import { makeConfig, makeLedger } from "../../test/factories";
import { renderWithProviders, stubApi } from "../../test/render";
import { LedgerPage } from "./LedgerPage";

afterEach(() => vi.restoreAllMocks());

const DOC_URL = "https://docs.google.com/document/d/EXAMPLE_DOCUMENT_ID/edit";

function show(ledger: LedgerView, docUrl: string | null = DOC_URL) {
  stubApi({ ledger, config: makeConfig({ doc_url: docUrl }) });
  return renderWithProviders(<LedgerPage />);
}

function mockClipboard() {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  return writeText;
}

describe("LedgerPage", () => {
  it("is read-only: a chip says so", async () => {
    show(makeLedger());
    expect(await screen.findByText("Read-only")).toBeInTheDocument();
  });

  it("lists weeks newest first with Doc and draft state, revision, characters, ids", async () => {
    show(makeLedger({ pending: true }));
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("2026-W43");
    expect(rows[0]).toHaveTextContent("Appended");
    expect(rows[0]).toHaveTextContent("rev_sample_43");
    expect(rows[0]).toHaveTextContent("1,184");
    expect(rows[0]).toHaveTextContent("Created");
    expect(rows[0]).toHaveTextContent("draft_sample_43");
    expect(rows[0]).toHaveTextContent("Complete");
    expect(rows[1]).toHaveTextContent("2026-W39");
    expect(rows[1]).toHaveTextContent("Pending");
    expect(rows[1]).toHaveTextContent("Action required");
  });

  it("links the run id to its detail page and builds the Doc link from config", async () => {
    show(makeLedger());
    const table = await screen.findByRole("table");
    expect(within(table).getByRole("link", { name: "20261022-121514" })).toHaveAttribute(
      "href",
      "/runs/20261022-121514",
    );
    expect(within(table).getByRole("link", { name: /open doc/i })).toHaveAttribute("href", DOC_URL);
  });

  it("has no Doc link when the config has no doc_url", async () => {
    show(makeLedger(), null);
    const table = await screen.findByRole("table");
    expect(within(table).queryByRole("link", { name: /open doc/i })).not.toBeInTheDocument();
  });

  it("tags a step confirmed by hand", async () => {
    const view = makeLedger();
    view.weeks["2026-W43"].draft!.confirmed_by_hand = true;
    show(view);
    expect(await screen.findByText("Confirmed by hand")).toBeInTheDocument();
  });

  it("shows a banner with the exact confirm and clear commands for a pending draft", async () => {
    const writeText = mockClipboard();
    show(makeLedger({ pending: true }));
    expect(await screen.findByText(/Outcome unknown: an earlier run died while writing/)).toBeInTheDocument();
    expect(screen.getByText(/Check the Doc or Drafts folder, then run one of these/)).toBeInTheDocument();
    const confirm = "python -m pulse ledger confirm 2026-W39 draft";
    const clear = "python -m pulse ledger clear 2026-W39 draft";
    expect(screen.getByText(confirm)).toBeInTheDocument();
    expect(screen.getByText(clear)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copy: it is there" }));
    expect(writeText).toHaveBeenLastCalledWith(confirm);
    await userEvent.click(screen.getByRole("button", { name: "Copy: it is not there" }));
    expect(writeText).toHaveBeenLastCalledWith(clear);
  });

  it("shows one banner per pending step", async () => {
    const view = makeLedger({ pending: true });
    view.weeks["2026-W39"].doc = { state: "pending", run_id: "20260924-090009" };
    show(view);
    await screen.findByRole("table");
    expect(screen.getAllByText(/Outcome unknown/)).toHaveLength(2);
    expect(screen.getByText("python -m pulse ledger confirm 2026-W39 doc")).toBeInTheDocument();
    expect(screen.getByText("python -m pulse ledger confirm 2026-W39 draft")).toBeInTheDocument();
  });

  it("shows no pending banner for a clean ledger", async () => {
    show(makeLedger());
    await screen.findByRole("table");
    expect(screen.queryByText(/Outcome unknown/)).not.toBeInTheDocument();
  });

  it("shows the empty state when there is no ledger", async () => {
    show({ weeks: {}, error: null });
    expect(await screen.findByText("Nothing published from this machine")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("never shows the empty state for an unreadable ledger", async () => {
    show({ weeks: {}, error: "ledger_unreadable" });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "The ledger file cannot be read. Duplicate protection is unknown until it is fixed or restored.",
    );
    expect(screen.queryByText("Nothing published from this machine")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("shows the resume command for a week whose draft is missing", async () => {
    const writeText = mockClipboard();
    show({
      error: null,
      weeks: {
        "2026-W40": {
          doc: { state: "appended", run_id: "20261001-090000", revision_id: "rev_40" },
          draft: null,
        },
      },
    });
    const table = await screen.findByRole("table");
    const command = "python -m pulse run --resume 20261001-090000";
    expect(within(table).getByText(command)).toBeInTheDocument();
    expect(within(table).getByText("Draft missing")).toBeInTheDocument();
    expect(within(table).getByText("Not started")).toBeInTheDocument();
    await userEvent.click(within(table).getByRole("button", { name: /copy/i }));
    expect(writeText).toHaveBeenCalledWith(command);
  });

  it("has no button in the table that is not a copy button", async () => {
    show({
      error: null,
      weeks: {
        ...makeLedger({ pending: true }).weeks,
        "2026-W40": { doc: { state: "appended", run_id: "20261001-090000" }, draft: null },
      },
    });
    const table = await screen.findByRole("table");
    const buttons = within(table).queryAllByRole("button");
    expect(buttons.length).toBeGreaterThan(0);
    for (const button of buttons) expect(button).toHaveTextContent(/copy/i);
  });

  it("explains that losing the ledger loses duplicate protection", async () => {
    show(makeLedger());
    expect(await screen.findByText(/losing data\/ledger\.json loses duplicate protection/i)).toBeInTheDocument();
    expect(screen.getByText(/back it up outside Git/i)).toBeInTheDocument();
  });

  it("says the ledger is unavailable when the request fails", async () => {
    stubApi({ config: makeConfig() });
    const { api } = await import("../../api/client");
    vi.spyOn(api, "getLedger").mockRejectedValue(new Error("down"));
    renderWithProviders(<LedgerPage />);
    expect(await screen.findByText(/ledger unavailable/i)).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = show(makeLedger({ pending: true }));
    await screen.findByRole("table");
    expect(await axe(container)).toHaveNoViolations();
  });
});
