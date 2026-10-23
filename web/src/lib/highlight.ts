import { normalize } from "./guardrails";

/**
 * Where `quote` sits in `text`, as `[start, end)` offsets into the original text, matching the
 * way the backend checks quotes: case, runs of whitespace, curly quotes and dashes are ignored.
 * Null when the quote is not in the text.
 */
export function findQuoteRange(text: string, quote: string): [number, number] | null {
  const needle = normalize(quote);
  if (!needle) return null;

  // Normalise the text one character at a time, remembering where each kept character came from.
  let folded = "";
  const origin: number[] = [];
  let lastWasSpace = true; // drops leading whitespace
  for (let i = 0; i < text.length; ) {
    const char = String.fromCodePoint(text.codePointAt(i)!);
    if (/\s/.test(char)) {
      if (!lastWasSpace) {
        folded += " ";
        origin.push(i);
        lastWasSpace = true;
      }
    } else {
      for (const piece of normalize(char)) {
        folded += piece;
        for (let k = 0; k < piece.length; k++) origin.push(i);
      }
      lastWasSpace = false;
    }
    i += char.length;
  }

  const at = folded.indexOf(needle);
  if (at < 0) return null;
  const start = origin[at];
  const lastChar = origin[at + needle.length - 1];
  const lastLength = String.fromCodePoint(text.codePointAt(lastChar)!).length;
  return [start, lastChar + lastLength];
}
