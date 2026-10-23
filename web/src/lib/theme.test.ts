import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DESKTOP_DARK, mockMatchMedia } from "../test/matchMedia";
import { useTheme } from "./theme";

afterEach(() => vi.restoreAllMocks());

describe("useTheme", () => {
  it("setTheme('dark') adds the dark class and persists", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme("dark"));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(result.current.resolved).toBe("dark");
    expect(localStorage.getItem("pulse-theme")).toBe("dark");
  });

  it("still applies the class when localStorage throws", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const { result } = renderHook(() => useTheme());
    expect(() => act(() => result.current.setTheme("dark"))).not.toThrow();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("follows prefers-color-scheme when set to system", () => {
    mockMatchMedia(DESKTOP_DARK);
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("system");
    expect(result.current.resolved).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("returns to light when switched from dark", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme("dark"));
    act(() => result.current.setTheme("light"));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
