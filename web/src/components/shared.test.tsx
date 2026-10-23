import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import type { RunStatus } from "../api/types";
import { Card } from "./Card";
import { ChartFrame } from "./ChartFrame";
import { CopyButton } from "./CopyButton";
import { DataUnavailable } from "./DataUnavailable";
import { Mono } from "./Mono";
import { Stars } from "./Stars";
import { StatusBadge } from "./StatusBadge";
import { ThemeChip } from "./ThemeChip";

const STATUSES: RunStatus[] = [
  "running",
  "completed",
  "failed_validation",
  "partial",
  "failed",
  "already_published",
  "interrupted",
  "unreadable",
];

describe("StatusBadge", () => {
  it.each(STATUSES)("%s has visible text and an icon, not colour alone", (status) => {
    const { container } = render(<StatusBadge status={status} run={{ doc_url: null }} />);
    expect(container.textContent?.trim().length).toBeGreaterThan(3);
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("says a completed run with no doc is a dry run, and one with a doc is not", () => {
    const { rerender } = render(<StatusBadge status="completed" run={{ doc_url: null }} />);
    expect(screen.getByText("Completed · Dry run, nothing published")).toBeInTheDocument();
    rerender(<StatusBadge status="completed" run={{ doc_url: "https://example.com/d" }} />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("does not claim a dry run when it has no run to look at", () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("gives Running a pulsing dot that stops under prefers-reduced-motion", () => {
    const { container } = render(<StatusBadge status="running" />);
    const dot = container.querySelector("[data-pulse-dot]");
    expect(dot).not.toBeNull();
    expect(dot!.className).toContain("animate-pulse");
    expect(dot!.className).toContain("motion-reduce:animate-none");
  });

  it("has no axe violations", async () => {
    const { container } = render(<StatusBadge status="failed" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("Stars", () => {
  it("shows the number to one decimal and an accessible label", () => {
    render(<Stars value={1.27} />);
    expect(screen.getByText("1.3")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "1.3 out of 5" })).toBeInTheDocument();
  });

  it("draws max stars, filled up to the rounded value", () => {
    const { container } = render(<Stars value={3.4} />);
    expect(container.querySelectorAll("svg")).toHaveLength(5);
    expect(container.querySelectorAll("svg[data-filled='true']")).toHaveLength(3);
  });

  it("respects max", () => {
    const { container } = render(<Stars value={2} max={3} />);
    expect(container.querySelectorAll("svg")).toHaveLength(3);
    expect(screen.getByRole("img", { name: "2.0 out of 3" })).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = render(<Stars value={4.2} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("ThemeChip, Card, Mono, DataUnavailable", () => {
  it("renders the theme label", () => {
    render(<ThemeChip themeId="customer-support" label="Customer Support" />);
    expect(screen.getByText("Customer Support")).toBeInTheDocument();
  });

  it("Card shows its title and eyebrow", () => {
    render(
      <Card title="Top themes" eyebrow="This week">
        <p>body</p>
      </Card>,
    );
    expect(screen.getByRole("heading", { name: "Top themes" })).toBeInTheDocument();
    expect(screen.getByText("This week")).toBeInTheDocument();
    expect(screen.getByText("body")).toBeInTheDocument();
  });

  it("Mono uses the code font", () => {
    render(<Mono>20261022-121514</Mono>);
    expect(screen.getByText("20261022-121514").className).toContain("font-data-code");
  });

  it("DataUnavailable says what is missing", () => {
    render(<DataUnavailable what="Funnel" />);
    expect(screen.getByText(/Funnel/)).toBeInTheDocument();
    expect(screen.getByText(/unavailable/i)).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = render(
      <main>
        <h1>Page</h1>
        <Card title="T" eyebrow="E">
          <ThemeChip themeId="a" label="A" /> <Mono>id</Mono> <DataUnavailable what="Thing" />
        </Card>
      </main>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("CopyButton", () => {
  let writeText: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("writes exactly the given text", async () => {
    const text = "python -m pulse run --resume 20261022-121514";
    render(<CopyButton text={text} />);
    await userEvent.click(screen.getByRole("button", { name: /copy/i }));
    expect(writeText).toHaveBeenCalledWith(text);
  });

  it("says Copied for two seconds, then goes back", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<CopyButton text="x" label="Copy note" />);
    await userEvent.click(screen.getByRole("button", { name: "Copy note" }));
    expect(await screen.findByText("Copied")).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(2100);
    });
    expect(screen.queryByText("Copied")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy note" })).toBeInTheDocument();
  });

  it("still renders and offers the text selected when the clipboard rejects", async () => {
    writeText.mockRejectedValue(new Error("denied"));
    render(<CopyButton text="select me" />);
    await userEvent.click(screen.getByRole("button", { name: /copy/i }));
    const field = (await screen.findByDisplayValue("select me")) as HTMLInputElement;
    expect(field).toHaveFocus();
    expect(field.selectionStart).toBe(0);
    expect(field.selectionEnd).toBe("select me".length);
    expect(screen.getByRole("button", { name: /copy/i })).toBeInTheDocument();
  });

  it("works when there is no clipboard API at all", async () => {
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
    render(<CopyButton text="plain" />);
    await userEvent.click(screen.getByRole("button", { name: /copy/i }));
    expect(await screen.findByDisplayValue("plain")).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    const { container } = render(<CopyButton text="x" />);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("ChartFrame", () => {
  const table = { columns: ["Rating", "Reviews"], rows: [["1", 120], ["5", 80]] as (string | number)[][] };

  it("toggles between the chart and a table of the same data", async () => {
    render(
      <ChartFrame title="Rating distribution" sampleNote="Analysed sample of 500" table={table}>
        <svg data-testid="chart" />
      </ChartFrame>,
    );
    expect(screen.getByTestId("chart")).toBeInTheDocument();
    expect(screen.getByText("Analysed sample of 500")).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "View as table" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByTestId("chart")).not.toBeInTheDocument();
    const grid = screen.getByRole("table");
    expect(grid).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Rating" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "120" })).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3);

    await userEvent.click(toggle);
    expect(screen.getByTestId("chart")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("has no axe violations in either view", async () => {
    const { container } = render(
      <ChartFrame title="Chart" table={table}>
        <svg role="img" aria-label="chart" />
      </ChartFrame>,
    );
    expect(await axe(container)).toHaveNoViolations();
    await userEvent.click(screen.getByRole("button", { name: "View as table" }));
    expect(await axe(container)).toHaveNoViolations();
  });
});
