import { describe, expect, it } from "vitest";
import { makeConfig, makeRanking } from "../test/factories";
import { splitSelected, weightedContributions } from "./themes";

describe("weightedContributions", () => {
  it("multiplies each component by its weight", () => {
    const ranking = makeRanking();
    const support = ranking.ranked.find((r) => r.theme.theme_id === "customer-support")!;
    const { weights } = makeConfig().ranking;
    const c = weightedContributions(support.components, weights);
    expect(c.volume.toFixed(3)).toBe("0.044");
    expect(c.recency.toFixed(3)).toBe("0.015");
    expect(c.severity.toFixed(3)).toBe("0.280");
    expect((c.volume + c.recency + c.severity).toFixed(3)).toBe("0.339");
    expect(c.volume + c.recency + c.severity).toBeCloseTo(support.score, 10);
  });

  it("uses the weights it is given, not constants", () => {
    const c = weightedContributions(
      { volume: 1, recency: 1, severity: 1 },
      { volume: 0.4, recency: 0.3, severity: 0.3 },
    );
    expect(c).toEqual({ volume: 0.4, recency: 0.3, severity: 0.3 });
  });
});

describe("splitSelected", () => {
  const { ranked, top } = makeRanking();
  const split = splitSelected(ranked, top);

  it("keeps Other out of the selection although it scores highest", () => {
    expect(ranked[0].theme.theme_id).toBe("other");
    expect(split.excludedOther.map((r) => r.theme.theme_id)).toEqual(["other"]);
    expect(split.selected.map((r) => r.theme.theme_id)).not.toContain("other");
  });

  it("orders the selection as the top list does", () => {
    expect(split.selected.map((r) => r.theme.theme_id)).toEqual([
      "customer-support",
      "trading-experience-and-app-performance",
      "payments-and-withdrawals",
    ]);
  });

  it("puts the rest in notSelected, in score order", () => {
    expect(split.notSelected.map((r) => r.theme.theme_id)).toEqual([
      "onboarding-and-kyc",
      "statements-and-reports",
    ]);
  });

  it("copes with a top id that is not ranked", () => {
    const odd = splitSelected(ranked, ["customer-support", "ghost"]);
    expect(odd.selected).toHaveLength(1);
  });
});
