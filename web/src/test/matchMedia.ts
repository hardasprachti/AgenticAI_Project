import { vi } from "vitest";

/** jsdom has no matchMedia. Install one whose `matches` is decided per query. */
export function mockMatchMedia(matches: (query: string) => boolean) {
  vi.stubGlobal(
    "matchMedia",
    (query: string): MediaQueryList =>
      ({
        matches: matches(query),
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList,
  );
}

/** Wide, light viewport: the default for every test. */
export const DESKTOP = (query: string) => query.includes("min-width");
/** Tablet-width viewport: below the 1280px sidebar breakpoint. */
export const TABLET = () => false;
/** Wide viewport that prefers a dark colour scheme. */
export const DESKTOP_DARK = (query: string) =>
  query.includes("min-width") || query.includes("prefers-color-scheme: dark");
