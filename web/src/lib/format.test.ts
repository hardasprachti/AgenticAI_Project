import { describe, expect, it } from "vitest";
import {
  formatDay,
  formatDuration,
  formatInt,
  formatIst,
  formatIstShort,
  formatPercent,
  formatWindow,
  isoWeekLabel,
  truncateId,
  windowWeeks,
} from "./format";

describe("formatInt", () => {
  it("groups thousands and shows a dash for null", () => {
    expect(formatInt(10332)).toBe("10,332");
    expect(formatInt(0)).toBe("0");
    expect(formatInt(1234567)).toBe("1,234,567");
    expect(formatInt(null)).toBe("—");
    expect(formatInt(NaN)).toBe("—");
  });
});

describe("formatPercent (takes a fraction)", () => {
  it("shows at most one decimal and drops a trailing .0", () => {
    expect(formatPercent(7303 / 10332)).toBe("70.7%");
    expect(formatPercent(3029 / 10332)).toBe("29.3%");
    expect(formatPercent(0.088)).toBe("8.8%");
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(1)).toBe("100%");
    expect(formatPercent(0)).toBe("0%");
  });

  it("honours the digits argument", () => {
    expect(formatPercent(0.0881, 0)).toBe("9%");
    expect(formatPercent(0.08812, 2)).toBe("8.81%");
  });

  it("shows a dash instead of NaN", () => {
    expect(formatPercent(NaN)).toBe("—");
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(Infinity)).toBe("—");
  });
});

describe("formatWindow / windowWeeks", () => {
  it("writes the window with a hyphen", () => {
    expect(formatWindow("2026-08-13", "2026-10-22")).toBe("13 Aug - 22 Oct 2026");
  });

  it("includes both years when the window crosses a year", () => {
    expect(formatWindow("2025-12-30", "2026-03-12")).toBe("30 Dec 2025 - 12 Mar 2026");
  });

  it("counts weeks", () => {
    expect(windowWeeks("2026-08-13", "2026-10-22")).toBe(10);
    expect(windowWeeks("2026-09-03", "2026-10-22")).toBe(7);
  });

  it("copes with garbage", () => {
    expect(formatWindow("nope", "2026-10-22")).toBe("—");
    expect(Number.isNaN(windowWeeks("nope", "2026-10-22"))).toBe(true);
  });
});

describe("formatDuration", () => {
  it("formats seconds, minutes and hours", () => {
    expect(formatDuration(435.81)).toBe("7m 16s");
    expect(formatDuration(72)).toBe("1m 12s");
    expect(formatDuration(4)).toBe("4s");
    expect(formatDuration(0)).toBe("0s");
    expect(formatDuration(59.6)).toBe("1m 0s");
    expect(formatDuration(3725)).toBe("1h 2m");
  });

  it("shows a dash for nonsense", () => {
    expect(formatDuration(NaN)).toBe("—");
    expect(formatDuration(-1)).toBe("—");
  });
});

describe("formatIst", () => {
  it("renders IST with UTC alongside", () => {
    expect(formatIst("2026-10-22T12:15:14.967424+00:00")).toEqual({
      ist: "22 Oct 2026, 17:45:14 IST",
      utc: "2026-10-22 12:15:14 UTC",
    });
  });

  it("rolls the date over after midnight IST", () => {
    expect(formatIst("2026-12-31T20:00:00Z").ist).toBe("1 Jan 2027, 01:30:00 IST");
  });

  it("accepts an offset in the input", () => {
    expect(formatIst("2026-10-22T17:45:14+05:30").utc).toBe("2026-10-22 12:15:14 UTC");
  });

  it("shows dashes for an invalid timestamp", () => {
    expect(formatIst("not a date")).toEqual({ ist: "—", utc: "—" });
  });
});

describe("truncateId", () => {
  it("keeps the first 6 and last 7 characters", () => {
    expect(truncateId("209a6622a2916a18")).toBe("209a66…2916a18");
  });

  it("leaves short ids alone", () => {
    expect(truncateId("abc123")).toBe("abc123");
  });
});

describe("isoWeekLabel", () => {
  it("labels the ISO week of a date, as the backend does", () => {
    expect(isoWeekLabel("2026-10-22")).toBe("2026-W43");
    expect(isoWeekLabel("2026-12-31")).toBe("2026-W53");
    expect(isoWeekLabel("2027-01-01")).toBe("2026-W53");
    expect(isoWeekLabel("2025-12-29")).toBe("2026-W01");
  });

  it("returns a dash for an unreadable date", () => {
    expect(isoWeekLabel("soon")).toBe("—");
  });
});

describe("formatDay", () => {
  it("writes a single date", () => {
    expect(formatDay("2026-08-10")).toBe("10 Aug 2026");
    expect(formatDay("x")).toBe("—");
  });
});

describe("formatIstShort", () => {
  it("is day, month and IST clock time", () => {
    expect(formatIstShort("2026-10-22T12:15:14Z")).toBe("22 Oct 17:45");
    expect(formatIstShort("nope")).toBe("—");
  });
});
