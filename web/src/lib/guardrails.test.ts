import { describe, expect, it } from "vitest";
import type { Pulse, ReviewRow, Run } from "../api/types";
import {
  makeConfig,
  makeFailedRun,
  makePulse,
  makeReviewsById,
  makeRun,
  withoutStage,
} from "../test/factories";
import { evaluateGuardrails, normalize, tallyGuardrails, type Guardrail } from "./guardrails";

type Input = Parameters<typeof evaluateGuardrails>[0];

function evaluate(overrides: Partial<Input> = {}): Record<string, Guardrail> {
  const result = evaluateGuardrails({
    run: makeRun(),
    pulse: makePulse(),
    reviewsById: makeReviewsById(),
    config: makeConfig(),
    ...overrides,
  });
  return Object.fromEntries(result.map((g) => [g.id, g]));
}

function withWindow(start: string, end: string): Pulse {
  return makePulse({ window_start: start, window_end: end });
}

describe("evaluateGuardrails on the real run", () => {
  it("returns the seven guardrails in order", () => {
    const ids = evaluateGuardrails({
      run: makeRun(),
      pulse: makePulse(),
      reviewsById: makeReviewsById(),
      config: makeConfig(),
    }).map((g) => g.id);
    expect(ids).toEqual(["themes", "quotes", "actions", "words", "identity", "window", "compose"]);
  });

  it("passes all seven", () => {
    const g = evaluate();
    for (const guardrail of Object.values(g)) {
      expect([guardrail.id, guardrail.status]).toEqual([guardrail.id, "pass"]);
    }
    expect(tallyGuardrails(Object.values(g))).toEqual({ pass: 7, fail: 0, unavailable: 0, total: 7 });
  });
});

describe("normalize", () => {
  it("collapses whitespace, lower-cases and folds curly quotes and dashes", () => {
    expect(normalize("  Don’t   STOP – now\n")).toBe("don't stop - now");
    expect(normalize("“Hi”  there")).toBe('"hi" there');
  });
});

describe("quotes", () => {
  function withReviewText(id: string, text: string): Record<string, ReviewRow> {
    const reviews = makeReviewsById();
    reviews[id] = { ...reviews[id], text };
    return reviews;
  }
  const firstQuote = makePulse().quotes[0];

  it("fails with detail (not a crash) when a quoted review is not in the analysed set", () => {
    const reviews = makeReviewsById();
    delete reviews[firstQuote.review_id];
    const g = evaluate({ reviewsById: reviews }).quotes;
    expect(g.status).toBe("fail");
    expect(g.detail).toMatch(/not in the analysed set/i);
    expect(g.detail).toContain("209a66…2916a18");
  });

  it("fails when the text differs by a word", () => {
    const reviews = withReviewText(
      firstQuote.review_id,
      "The customer service is bad. I don't get any reply even though it say 24/7 support",
    );
    expect(evaluate({ reviewsById: reviews }).quotes.status).toBe("fail");
  });

  it("passes when the only differences are double spaces, case and a curly apostrophe", () => {
    const reviews = withReviewText(
      firstQuote.review_id,
      "THE customer  service is worst.   I don’t get any reply even though it say 24/7 support!",
    );
    expect(evaluate({ reviewsById: reviews }).quotes.status).toBe("pass");
  });

  it("is unavailable while the reviews have not loaded", () => {
    expect(evaluate({ reviewsById: null }).quotes.status).toBe("unavailable");
  });

  it("fails when there are not three quotes", () => {
    const pulse = makePulse();
    pulse.quotes = pulse.quotes.slice(0, 2);
    expect(evaluate({ pulse }).quotes.status).toBe("fail");
  });
});

describe("themes", () => {
  it("counts clustering themes without Other (5 of max 5 passes)", () => {
    const g = evaluate({ config: makeConfig({ max_themes: 5 }) }).themes;
    expect(g.status).toBe("pass");
    expect(g.detail).toContain("5");
  });

  it("fails with a sixth clustering theme", () => {
    const run = makeRun();
    run.theme_scores["extra-theme"] = { ...run.theme_scores["customer-support"] };
    expect(evaluate({ run }).themes.status).toBe("fail");
  });

  it("takes the cap from config, not a constant", () => {
    expect(evaluate({ config: makeConfig({ max_themes: 4 }) }).themes.status).toBe("fail");
  });

  it("fails when the note does not have three themes", () => {
    const pulse = makePulse();
    pulse.themes = pulse.themes.slice(0, 2);
    expect(evaluate({ pulse }).themes.status).toBe("fail");
  });

  it("is unavailable when the run has no theme scores", () => {
    expect(evaluate({ run: makeRun({ theme_scores: {} }) }).themes.status).toBe("unavailable");
  });
});

describe("actions", () => {
  it("fails when an action references a theme outside the top three", () => {
    const pulse = makePulse();
    pulse.actions[1] = { ...pulse.actions[1], theme_id: "onboarding-and-kyc" };
    const g = evaluate({ pulse }).actions;
    expect(g.status).toBe("fail");
    expect(g.detail).toContain("onboarding-and-kyc");
  });

  it("fails when there are not three actions", () => {
    const pulse = makePulse();
    pulse.actions = pulse.actions.slice(0, 1);
    expect(evaluate({ pulse }).actions.status).toBe("fail");
  });
});

describe("words", () => {
  it("compares word_count with max_words from config", () => {
    expect(evaluate().words.detail).toContain("192");
    expect(evaluate({ run: makeRun({ word_count: 250 }) }).words.status).toBe("pass");
    expect(evaluate({ run: makeRun({ word_count: 251 }) }).words.status).toBe("fail");
    const tight = makeConfig();
    tight.pulse.max_words = 150;
    expect(evaluate({ config: tight }).words.status).toBe("fail");
  });
});

describe("window", () => {
  it("passes at 10 weeks and at the 8 and 12 week bounds", () => {
    expect(evaluate().window.status).toBe("pass");
    expect(evaluate({ pulse: withWindow("2026-08-27", "2026-10-22") }).window.status).toBe("pass");
    expect(evaluate({ pulse: withWindow("2026-07-30", "2026-10-22") }).window.status).toBe("pass");
  });

  it("fails at 7 weeks and at 13 weeks", () => {
    expect(evaluate({ pulse: withWindow("2026-09-03", "2026-10-22") }).window.status).toBe("fail");
    expect(evaluate({ pulse: withWindow("2026-07-23", "2026-10-22") }).window.status).toBe("fail");
  });
});

describe("identity", () => {
  it("shows the five redaction counts and never fails", () => {
    const g = evaluate().identity;
    expect(g.status).toBe("pass");
    expect(g.detail).toContain("34");
    expect(g.items).toEqual([
      "34 reviewer names",
      "3 emails",
      "3 handles",
      "2 ID tokens",
      "3 numbers",
    ]);
    const heavy = makeRun();
    heavy.stages[1].counts.redacted_email = 9999;
    expect(evaluate({ run: heavy }).identity.status).toBe("pass");
  });

  it("is unavailable when there is no sanitize stage", () => {
    expect(evaluate({ run: withoutStage(makeRun(), "sanitize") }).identity.status).toBe(
      "unavailable",
    );
  });
});

describe("compose", () => {
  it("shows retries 0 for the real run", () => {
    const g = evaluate().compose;
    expect(g.status).toBe("pass");
    expect(g.detail).toMatch(/retries: 0/i);
  });

  it("lists violations and fails a failed_validation run", () => {
    const run = makeRun({
      status: "failed_validation",
      retries: 2,
      violations: ["[word_limit] 312 words, limit is 250"],
    });
    const g = evaluate({ run }).compose;
    expect(g.status).toBe("fail");
    expect(g.items).toEqual(["[word_limit] 312 words, limit is 250"]);
    expect(g.detail).toMatch(/retries: 2/i);
  });

  it("passes with a retry when the note finally validated", () => {
    const g = evaluate({ run: makeRun({ retries: 1 }) }).compose;
    expect(g.status).toBe("pass");
    expect(g.detail).toMatch(/retries: 1/i);
  });
});

describe("when there is no pulse", () => {
  const failed: Run = makeFailedRun();
  const g = evaluate({ run: failed, pulse: null, reviewsById: null });

  it("makes every pulse-dependent guardrail unavailable", () => {
    for (const id of ["themes", "quotes", "actions", "words", "window"]) {
      expect([id, g[id].status]).toEqual([id, "unavailable"]);
    }
  });

  it("never counts an unavailable guardrail as a pass", () => {
    const tally = tallyGuardrails(Object.values(g));
    expect(tally.unavailable).toBeGreaterThanOrEqual(5);
    expect(tally.pass + tally.fail + tally.unavailable).toBe(tally.total);
    expect(tally.pass).toBeLessThanOrEqual(tally.total - 5);
  });

  it("still describes identity from the sanitize counts", () => {
    expect(g.identity.status).toBe("pass");
  });

  it("does not claim compose passed when compose never ran", () => {
    expect(g.compose.status).toBe("unavailable");
  });
});

describe("no run at all", () => {
  it("makes everything unavailable", () => {
    const g = evaluate({ run: null, pulse: null, reviewsById: null });
    expect(Object.values(g).every((x) => x.status === "unavailable")).toBe(true);
  });
});
