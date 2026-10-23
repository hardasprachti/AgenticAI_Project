import { describe, expect, it } from "vitest";
import { contrastRatio, darkColors, lightColors, statusDark, statusLight } from "./tokens";

const MIN = 4.5;

const textPairs: [string, string][] = [
  ["on-surface", "surface"],
  ["primary", "surface-container-lowest"],
  ["on-primary-container", "primary-container"],
  ["secondary", "surface"],
];

describe("contrastRatio", () => {
  it("is 21 for black on white and 1 for identical colours", () => {
    expect(contrastRatio("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contrastRatio("#00b386", "#00b386")).toBeCloseTo(1, 5);
  });
});

describe.each([
  ["light", lightColors, statusLight],
  ["dark", darkColors, statusDark],
] as const)("%s tokens", (_name, colors, status) => {
  it.each(textPairs)("%s on %s meets 4.5:1", (fg, bg) => {
    const ratio = contrastRatio(
      colors[fg as keyof typeof colors],
      colors[bg as keyof typeof colors],
    );
    expect(ratio).toBeGreaterThanOrEqual(MIN);
  });

  it.each(Object.keys(status))(
    "status %s text on its badge background meets 4.5:1 at 11px",
    (key) => {
      const pair = status[key as keyof typeof status];
      expect(contrastRatio(pair.fg, pair.bg)).toBeGreaterThanOrEqual(MIN);
    },
  );
});
