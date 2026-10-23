import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { ReviewRow } from "../../api/types";
import { makeConfig, makePulse, makeRanking, makeReviewsById } from "../../test/factories";
import { renderWithProviders, stubApi } from "../../test/render";
import { ActionCards } from "./ActionCards";
import { QuoteCards } from "./QuoteCards";
import { ThemeCards } from "./ThemeCards";

afterEach(() => vi.restoreAllMocks());

const RUN_ID = "20261022-121514";

describe("ThemeCards", () => {
  function renderThemes(config = makeConfig()) {
    stubApi();
    return renderWithProviders(
      <ThemeCards pulse={makePulse()} ranking={makeRanking()} config={config} />,
    );
  }

  it("shows three cards in score order, Customer Support first", () => {
    renderThemes();
    const cards = screen.getAllByRole("article");
    expect(cards).toHaveLength(3);
    expect(within(cards[0]).getByRole("heading", { name: "Customer Support" })).toBeInTheDocument();
    expect(within(cards[1]).getByRole("heading", { name: /Trading Experience/ })).toBeInTheDocument();
    expect(within(cards[2]).getByRole("heading", { name: "Payments and Withdrawals" })).toBeInTheDocument();
  });

  it("states the share of the analysed sample, the count, the rating and the score", () => {
    renderThemes();
    const first = screen.getAllByRole("article")[0];
    expect(first).toHaveTextContent("8.8% of analysed reviews");
    expect(first).toHaveTextContent("44 of 500");
    expect(within(first).getByRole("img", { name: "1.3 out of 5" })).toBeInTheDocument();
    expect(first).toHaveTextContent("0.339");
    expect(first).toHaveTextContent("Users experience unresponsive or slow customer support");
  });

  it("footnotes that the published note calls this % of reviews", () => {
    renderThemes();
    expect(screen.getByText(/published note labels this/i)).toHaveTextContent('"% of reviews"');
  });

  it("explains the score with the weights from config, not constants", () => {
    const { unmount } = renderThemes();
    expect(screen.getAllByText("0.5 × volume + 0.2 × recency + 0.3 × severity")).toHaveLength(3);
    unmount();
    const config = makeConfig();
    config.ranking.weights = { volume: 0.4, recency: 0.3, severity: 0.3 };
    renderThemes(config);
    expect(screen.getAllByText("0.4 × volume + 0.3 × recency + 0.3 × severity")).toHaveLength(3);
    expect(screen.queryByText(/0\.5 × volume/)).not.toBeInTheDocument();
  });

  it("lists each contribution beside the bar", () => {
    renderThemes();
    const first = screen.getAllByRole("article")[0];
    expect(first).toHaveTextContent("Volume 0.044");
    expect(first).toHaveTextContent("Recency 0.015");
    expect(first).toHaveTextContent("Severity 0.280");
  });

  it("has a table view of the breakdown", async () => {
    renderThemes();
    const first = screen.getAllByRole("article")[0];
    await userEvent.click(within(first).getByRole("button", { name: "View as table" }));
    expect(within(first).getByRole("table")).toHaveTextContent("0.280");
  });

  it("has no axe violations", async () => {
    const { container } = renderThemes();
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("QuoteCards and the source drawer", () => {
  const quote = makePulse().quotes[0];
  const stored = (text: string): ReviewRow => ({
    ...makeReviewsById()[quote.review_id],
    text,
  });

  function renderQuotes(items: ReviewRow[]) {
    stubApi({ reviews: () => ({ items, total: items.length, page: 1, page_size: 25 }) });
    return renderWithProviders(<QuoteCards pulse={makePulse()} runId={RUN_ID} />);
  }

  it("shows each quote verbatim with its stars, theme and truncated review id", () => {
    renderQuotes([]);
    const cards = screen.getAllByRole("listitem");
    expect(cards).toHaveLength(3);
    expect(cards[0]).toHaveTextContent(quote.text);
    expect(cards[0]).toHaveTextContent("Customer Support");
    expect(cards[0]).toHaveTextContent("209a66…2916a18");
    expect(within(cards[0]).getByRole("img", { name: "1.0 out of 5" })).toBeInTheDocument();
  });

  it("opens the source review with the quote marked, even if the stored text has double spaces", async () => {
    renderQuotes([
      stored("Honestly  The customer   service is worst.  I don't get any reply even though it say 24/7 support!!"),
    ]);
    await userEvent.click(screen.getAllByRole("button", { name: /open source review/i })[0]);
    const drawer = await screen.findByRole("dialog", { name: /source review/i });
    const mark = await within(drawer).findByText((_, el) => el?.tagName === "MARK");
    expect(mark).toHaveTextContent(quote.text);
    expect(mark.textContent).toContain("customer   service"); // original spacing kept
    expect(drawer).toHaveTextContent("Honestly");
  });

  it("shows rating, date, app version and theme, but no device or reviewer", async () => {
    const review = stored(quote.text);
    renderQuotes([review]);
    await userEvent.click(screen.getAllByRole("button", { name: /open source review/i })[0]);
    const drawer = await screen.findByRole("dialog", { name: /source review/i });
    await within(drawer).findByText((_, el) => el?.tagName === "MARK");
    expect(drawer).toHaveTextContent(review.date as string);
    expect(drawer).toHaveTextContent(review.app_version as string);
    expect(drawer).toHaveTextContent("Customer Support");
    expect(drawer).not.toHaveTextContent(/device|android|ios|reviewer/i);
  });

  it("falls back when the source review is not in the analysed set", async () => {
    renderQuotes([]);
    await userEvent.click(screen.getAllByRole("button", { name: /open source review/i })[0]);
    expect(await screen.findByText("Source review not in the analysed set")).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    renderQuotes([stored(quote.text)]);
    await userEvent.click(screen.getAllByRole("button", { name: /open source review/i })[0]);
    await screen.findByRole("dialog", { name: /source review/i });
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("has no axe violations, closed and open", async () => {
    const { container } = renderQuotes([stored(quote.text)]);
    expect(await axe(container)).toHaveNoViolations();
    await userEvent.click(screen.getAllByRole("button", { name: /open source review/i })[0]);
    const drawer = await screen.findByRole("dialog", { name: /source review/i });
    await within(drawer).findByText((_, el) => el?.tagName === "MARK");
    expect(await axe(drawer)).toHaveNoViolations();
  });
});

describe("ActionCards", () => {
  it("shows number, text and theme chip, and nothing invented", () => {
    renderWithProviders(<ActionCards pulse={makePulse()} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("1");
    expect(items[0]).toHaveTextContent("Audit response times and add a live chat channel");
    expect(items[0]).toHaveTextContent("Customer Support");
    expect(document.body).not.toHaveTextContent(/impact|t-shirt|pod|owner/i);
  });

  it("has no axe violations", async () => {
    const { container } = renderWithProviders(<ActionCards pulse={makePulse()} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
