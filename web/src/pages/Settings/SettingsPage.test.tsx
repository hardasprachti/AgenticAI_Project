import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { makeConfig } from "../../test/factories";
import { renderWithProviders, stubApi } from "../../test/render";
import { SettingsPage } from "./SettingsPage";

afterEach(() => vi.restoreAllMocks());

async function show(config = makeConfig()) {
  stubApi({ config });
  const view = renderWithProviders(<SettingsPage />);
  await screen.findByRole("heading", { name: "Settings" });
  await screen.findByText("com.nextbillion.groww");
  return { ...view, config };
}

describe("SettingsPage", () => {
  it("shows every configured value", async () => {
    const { config } = await show();
    const page = document.body;
    expect(page).toHaveTextContent(config.app.play_package);
    expect(page).toHaveTextContent(`${config.app.play_lang} / ${config.app.play_country}`);
    expect(page).toHaveTextContent(`${config.window_weeks} weeks`);
    expect(screen.getByTestId("max-themes")).toHaveTextContent(String(config.max_themes));
    for (const label of config.taxonomy) expect(page).toHaveTextContent(label);
    expect(screen.getByTestId("weights")).toHaveTextContent("0.5");
    expect(screen.getByTestId("weights")).toHaveTextContent("0.2");
    expect(screen.getByTestId("weights")).toHaveTextContent("0.3");
    expect(screen.getByTestId("recency-window")).toHaveTextContent(
      `${config.ranking.recency_window_weeks} weeks`,
    );
    expect(screen.getByTestId("max-words")).toHaveTextContent(String(config.pulse.max_words));
    expect(screen.getByTestId("min-reviews")).toHaveTextContent(String(config.pulse.min_reviews));
    expect(screen.getByTestId("min-words")).toHaveTextContent(String(config.pulse.min_words));
    expect(screen.getByTestId("max-analysed")).toHaveTextContent(String(config.pulse.max_analysed));
    expect(page).toHaveTextContent(config.models.theme_assign as string);
    expect(page).toHaveTextContent(config.models.compose as string);
    expect(screen.getByTestId("batch-size")).toHaveTextContent(String(config.batch_size));
  });

  it("links the Doc with the config doc_url", async () => {
    const { config } = await show(makeConfig({ doc_url: "https://docs.google.com/document/d/abc/edit" }));
    const link = screen.getByRole("link", { name: /google doc/i });
    expect(link).toHaveAttribute("href", config.doc_url as string);
  });

  it("shows the draft recipient, or a dash when none is set", async () => {
    const { unmount } = await show(makeConfig({ draft_to: "product-leads@example.com" }));
    expect(screen.getByTestId("draft-to")).toHaveTextContent("product-leads@example.com");
    unmount();
    await show(makeConfig({ draft_to: null }));
    expect(screen.getByTestId("draft-to")).toHaveTextContent("—");
  });

  it("is read-only: no input, select, textarea or save button", async () => {
    await show();
    const main = document.body;
    expect(main.querySelector("input, select, textarea")).toBeNull();
    expect(screen.queryByRole("button", { name: /save|apply|update/i })).not.toBeInTheDocument();
  });

  it("states that secrets and paths are never shown, and shows neither", async () => {
    await show();
    expect(screen.getByText(/never shows secrets or file paths/i)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/server_dir|GROQ/i);
  });

  it("says models are configured now, not recorded per run", async () => {
    await show();
    expect(screen.getByText(/configured now/i)).toBeInTheDocument();
  });

  it("says settings are unavailable when the config cannot load", async () => {
    stubApi();
    const { api } = await import("../../api/client");
    vi.spyOn(api, "getConfig").mockRejectedValue(new Error("down"));
    renderWithProviders(<SettingsPage />);
    expect(await screen.findByText(/settings unavailable/i)).toBeInTheDocument();
  });

  it("has definition lists, and no axe violations", async () => {
    const { container } = await show();
    expect(within(container).getAllByRole("term").length).toBeGreaterThan(10);
    expect(await axe(container)).toHaveNoViolations();
  });
});
