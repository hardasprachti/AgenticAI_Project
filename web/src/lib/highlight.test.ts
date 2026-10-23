import { describe, expect, it } from "vitest";
import { findQuoteRange } from "./highlight";

const quote = "The customer service is worst. I don't get any reply";

function marked(text: string, q = quote): string | null {
  const range = findQuoteRange(text, q);
  return range ? text.slice(range[0], range[1]) : null;
}

describe("findQuoteRange", () => {
  it("finds an exact quote", () => {
    expect(marked(`Bad. ${quote} at all.`)).toBe(quote);
  });

  it("returns offsets into the original text, double spaces and all", () => {
    const text = "Ugh!  The customer   service is worst.  I don't get any reply, ever";
    expect(marked(text)).toBe("The customer   service is worst.  I don't get any reply");
  });

  it("ignores case", () => {
    expect(marked("THE CUSTOMER SERVICE IS WORST. I DON'T GET ANY REPLY")).toBe(
      "THE CUSTOMER SERVICE IS WORST. I DON'T GET ANY REPLY",
    );
  });

  it("matches a curly apostrophe against a straight one, and newlines against spaces", () => {
    expect(marked("The customer service is worst.\nI don’t get any reply")).toBe(
      "The customer service is worst.\nI don’t get any reply",
    );
  });

  it("finds a quote that starts the text and one that ends it", () => {
    expect(marked(quote)).toBe(quote);
    expect(marked(`x ${quote}`)).toBe(quote);
  });

  it("returns null when the quote is not there, or empty", () => {
    expect(findQuoteRange("Something else entirely", quote)).toBeNull();
    expect(findQuoteRange("anything", "   ")).toBeNull();
  });
});
