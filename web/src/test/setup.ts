import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, expect } from "vitest";
import * as axeMatchers from "vitest-axe/matchers";
import { DESKTOP, mockMatchMedia } from "./matchMedia";

expect.extend(axeMatchers);

beforeEach(() => {
  mockMatchMedia(DESKTOP);
});

afterEach(() => {
  cleanup();
  document.documentElement.classList.remove("dark");
  try {
    localStorage.clear();
  } catch {
    /* storage unavailable */
  }
});

// axe probes canvas for icon-ligature detection; jsdom does not implement it.
HTMLCanvasElement.prototype.getContext = (() => null) as typeof HTMLCanvasElement.prototype.getContext;

// Recharts' ResponsiveContainer observes its parent's size; jsdom has no ResizeObserver.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
