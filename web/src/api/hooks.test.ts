import { describe, expect, it } from "vitest";
import { ACTIVE_POLL_MS, activePollInterval } from "./hooks";
import type { ActiveRun } from "./types";

const idle: ActiveRun = {
  active: false,
  elapsed_s: null,
  last_line: null,
  started_by_api: false,
  exit_code: null,
  exit_message: null,
  new_run_id: null,
  stderr_tail: [],
};

describe("activePollInterval", () => {
  it("polls every 5 s only while a run is active", () => {
    expect(activePollInterval({ ...idle, active: true })).toBe(ACTIVE_POLL_MS);
    expect(ACTIVE_POLL_MS).toBe(5000);
  });

  it("does not poll when idle, finished or not yet loaded", () => {
    expect(activePollInterval(idle)).toBe(false);
    expect(activePollInterval({ ...idle, exit_code: 0 })).toBe(false);
    expect(activePollInterval(undefined)).toBe(false);
  });
});
