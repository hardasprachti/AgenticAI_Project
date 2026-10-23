import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { api, ApiError } from "../api/client";
import type { ActiveRun } from "../api/types";
import { IDLE, renderWithProviders, stubApi } from "../test/render";
import { RunControl } from "./RunControl";

const ACTIVE: ActiveRun = {
  ...IDLE,
  active: true,
  elapsed_s: 65,
  started_by_api: true,
  last_line: "Stage 3/6: theme",
};

function setup(active: ActiveRun = IDLE, onClose = vi.fn()) {
  stubApi({ active });
  const start = vi
    .spyOn(api, "startRun")
    .mockResolvedValue({ pid: 1, started_at: "2026-10-22T12:00:00Z" });
  const view = renderWithProviders(<RunControl open onClose={onClose} />);
  return { start, onClose, ...view };
}

afterEach(() => vi.restoreAllMocks());

describe("RunControl", () => {
  it("defaults to a Play Store dry run and sends no confirm", async () => {
    const { start } = setup();
    expect(await screen.findByRole("switch", { name: /dry run/i })).toBeChecked();
    await userEvent.click(screen.getByRole("button", { name: "Start dry run" }));
    await waitFor(() => expect(start).toHaveBeenCalledTimes(1));
    expect(start).toHaveBeenCalledWith({ source: "play", dry_run: true });
    expect(start.mock.calls[0][0]).not.toHaveProperty("confirm");
  });

  it("sends the chosen source and as-of date", async () => {
    const { start } = setup();
    await userEvent.selectOptions(await screen.findByLabelText("Source"), "csv");
    await userEvent.type(screen.getByLabelText(/as of/i), "2026-10-01");
    await userEvent.click(screen.getByRole("button", { name: "Start dry run" }));
    await waitFor(() => expect(start).toHaveBeenCalled());
    expect(start).toHaveBeenCalledWith({ source: "csv", dry_run: true, as_of: "2026-10-01" });
  });

  it("limits the as-of date to today", async () => {
    setup();
    const input = (await screen.findByLabelText(/as of/i)) as HTMLInputElement;
    expect(input.max).toBe(new Date().toISOString().slice(0, 10));
  });

  describe("publishing", () => {
    async function toDialog() {
      const view = setup();
      await userEvent.click(await screen.findByRole("switch", { name: /dry run/i }));
      await userEvent.click(screen.getByRole("button", { name: "Review and publish…" }));
      return view;
    }

    it("sends nothing until the dialog is confirmed, then sends confirm", async () => {
      const { start } = await toDialog();
      const dialog = await screen.findByRole("alertdialog");
      expect(start).not.toHaveBeenCalled();
      expect(dialog).toHaveTextContent(/appends a section to the Google Doc/i);
      expect(dialog).toHaveTextContent(/creates a Gmail draft/i);
      expect(dialog).toHaveTextContent(/nothing is emailed/i);
      await userEvent.click(within(dialog).getByRole("button", { name: /^Publish week / }));
      await waitFor(() => expect(start).toHaveBeenCalledTimes(1));
      expect(start).toHaveBeenCalledWith({ source: "play", dry_run: false, confirm: "publish" });
    });

    it("names the week on the confirm button", async () => {
      await toDialog();
      const dialog = await screen.findByRole("alertdialog");
      expect(within(dialog).getByRole("button", { name: /^Publish week \d{4}-W\d{2}$/ })).toBeInTheDocument();
    });

    it("sends nothing on Cancel, and the toggle stays off", async () => {
      const { start } = await toDialog();
      const dialog = await screen.findByRole("alertdialog");
      await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
      expect(start).not.toHaveBeenCalled();
      expect(screen.getByRole("switch", { name: /dry run/i })).not.toBeChecked();
    });

    it("sends nothing on Escape", async () => {
      const { start } = await toDialog();
      await screen.findByRole("alertdialog");
      await userEvent.keyboard("{Escape}");
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
      expect(start).not.toHaveBeenCalled();
    });

    it("resets the toggle to ON the next time it opens", async () => {
      stubApi();
      const { rerender } = renderWithProviders(<RunControl open onClose={() => {}} />);
      await userEvent.click(await screen.findByRole("switch", { name: /dry run/i }));
      expect(screen.getByRole("switch", { name: /dry run/i })).not.toBeChecked();
      rerender(<RunControl open={false} onClose={() => {}} />);
      rerender(<RunControl open onClose={() => {}} />);
      expect(await screen.findByRole("switch", { name: /dry run/i })).toBeChecked();
    });

    it("traps focus in the confirmation dialog and has no axe violations", async () => {
      await toDialog();
      const dialog = await screen.findByRole("alertdialog");
      const buttons = within(dialog).getAllByRole("button");
      await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true));
      for (let i = 0; i < buttons.length + 2; i++) {
        await userEvent.tab();
        expect(dialog.contains(document.activeElement)).toBe(true);
      }
      await userEvent.tab({ shift: true });
      expect(dialog.contains(document.activeElement)).toBe(true);
      expect(await axe(dialog)).toHaveNoViolations();
    });
  });

  it("starts only once on a double click", async () => {
    let release: () => void = () => {};
    const { start } = setup();
    start.mockImplementation(
      () => new Promise((resolve) => { release = () => resolve({ pid: 1, started_at: "x" }); }),
    );
    const button = await screen.findByRole("button", { name: "Start dry run" });
    await userEvent.dblClick(button);
    expect(start).toHaveBeenCalledTimes(1);
    expect(button).toBeDisabled();
    await act(async () => release());
  });

  it("disables submit and shows the timer and last line while a run is active", async () => {
    const { start } = setup(ACTIVE);
    expect(await screen.findByText("Stage 3/6: theme")).toBeInTheDocument();
    expect(screen.getByText(/1m 5s/)).toBeInTheDocument();
    expect(screen.getByText(/usually 6-8 minutes/)).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "Start dry run" });
    expect(submit).toBeDisabled();
    await userEvent.click(submit);
    expect(start).not.toHaveBeenCalled();
  });

  it("shows the ledger message for exit code 3", async () => {
    setup({
      ...IDLE,
      started_by_api: true,
      exit_code: 3,
      exit_message:
        "Stopped: a ledger step is pending. Check the Doc or Drafts folder, then use the ledger commands",
    });
    expect(await screen.findByText(/a ledger step is pending/)).toBeInTheDocument();
  });

  it("shows the finish message with a link to the new run, and refreshes the run lists", async () => {
    stubApi({
      active: { ...IDLE, started_by_api: true, exit_code: 0, exit_message: "Run finished", new_run_id: "20261023-090000" },
    });
    const { client } = renderWithProviders(<RunControl open onClose={() => {}} />);
    const invalidate = vi.spyOn(client, "invalidateQueries");
    expect(await screen.findByText("Run finished")).toBeInTheDocument();
    const link = await screen.findByRole("link", { name: "Go to run" });
    expect(link).toHaveAttribute("href", "/runs/20261023-090000");
    await waitFor(() => expect(invalidate).toHaveBeenCalled());
  });

  it("shows the last stderr lines when the run failed", async () => {
    setup({
      ...IDLE,
      started_by_api: true,
      exit_code: 1,
      exit_message: "Run failed, was partial, or failed validation. See the run record",
      stderr_tail: ["LLMError: Groq tokens-per-day limit reached"],
    });
    expect(await screen.findByText(/Groq tokens-per-day limit reached/)).toBeInTheDocument();
  });

  it("explains a 409", async () => {
    const { start } = setup();
    start.mockRejectedValue(new ApiError(409, "A run is already in progress"));
    await userEvent.click(await screen.findByRole("button", { name: "Start dry run" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A run is already in progress");
  });

  it("closes on Escape and has no axe violations", async () => {
    const { onClose } = setup();
    const dialog = await screen.findByRole("dialog");
    expect(await axe(dialog)).toHaveNoViolations();
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("renders nothing when closed", () => {
    stubApi();
    renderWithProviders(<RunControl open={false} onClose={() => {}} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
