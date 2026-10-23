import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { mockMatchMedia, TABLET } from "../test/matchMedia";
import { renderWithProviders, stubApi } from "../test/render";
import { AppShell } from "./AppShell";

function renderShell(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppShell>
        <h1>Page body</h1>
      </AppShell>
    </MemoryRouter>,
  );
}

const LABELS = ["Overview", "Run Detail", "Run History", "Publishing Ledger", "Settings"];

describe("AppShell", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("shows a Mock data pill only in mock mode", () => {
    const { unmount } = renderShell();
    expect(screen.queryByText("Mock data")).not.toBeInTheDocument();
    unmount();
    vi.stubEnv("VITE_MOCK", "1");
    renderShell();
    expect(screen.getByText("Mock data")).toBeInTheDocument();
  });

  it("shows the five navigation labels on a wide viewport", () => {
    renderShell();
    const nav = screen.getByRole("navigation", { name: "Main" });
    for (const label of LABELS) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.queryByRole("button", { name: "Open navigation" })).not.toBeInTheDocument();
  });

  it("marks only the active route with aria-current=page", () => {
    renderShell("/ledger");
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Publishing Ledger" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "Overview" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(nav.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  });

  it("treats /runs/<id> as Run Detail and /runs as Run History", () => {
    const { unmount } = renderShell("/runs/20261022-121514");
    expect(screen.getByRole("link", { name: "Run Detail" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Run History" })).not.toHaveAttribute(
      "aria-current",
    );
    unmount();
    renderShell("/runs");
    expect(screen.getByRole("link", { name: "Run History" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("makes the skip link the first focusable element and targets main content", async () => {
    renderShell();
    await userEvent.tab();
    const skip = screen.getByRole("link", { name: "Skip to content" });
    expect(skip).toHaveFocus();
    expect(skip).toHaveAttribute("href", "#main");
    expect(document.getElementById("main")).toContainElement(
      screen.getByRole("heading", { name: "Page body" }),
    );
  });

  it("hides the sidebar behind 'Open navigation' below 1280px", async () => {
    mockMatchMedia(TABLET);
    renderShell();
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect(within(nav).getByRole("link", { name: "Run History" })).toBeInTheDocument();
  });

  it("closes the drawer on Escape and after choosing a destination", async () => {
    mockMatchMedia(TABLET);
    renderShell();
    await userEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    await userEvent.click(screen.getByRole("link", { name: "Settings" }));
    expect(screen.queryByRole("navigation", { name: "Main" })).not.toBeInTheDocument();
  });

  it("lets the person switch theme from the top bar", async () => {
    renderShell();
    await userEvent.click(screen.getByRole("button", { name: /theme/i }));
    await userEvent.click(screen.getByRole("menuitemradio", { name: "Dark" }));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("has no axe violations", async () => {
    const { container } = renderShell();
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("AppShell run control", () => {
  afterEach(() => vi.restoreAllMocks());

  it("opens the run control from the New Run (Dry Run) button", async () => {
    stubApi();
    renderWithProviders(
      <AppShell>
        <h1>Page body</h1>
      </AppShell>,
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "New Run (Dry Run)" }));
    const dialog = await screen.findByRole("dialog", { name: "New run" });
    expect(within(dialog).getByRole("switch", { name: /dry run/i })).toBeChecked();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
