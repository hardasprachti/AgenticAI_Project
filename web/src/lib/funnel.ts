import { STAGE_NAMES, type Run, type StageName } from "../api/types";

export interface Funnel {
  fetched: number | null;
  pages: number | null;
  itemsSeen: number | null;
  outsideWindow: number | null;
  dropped: {
    short: number | null;
    nonEnglish: number | null;
    duplicate: number | null;
    invalid: number | null;
    /** Null unless all four reasons are recorded. */
    total: number | null;
  };
  clean: number | null;
  analysed: number | null;
  /** True when the model saw fewer reviews than were clean. */
  sampled: boolean;
  /** Clean reviews above the minimum needed to publish. */
  marginOverMin: number | null;
  /** Fractions (0-1), or null when the denominator is missing or zero. */
  pct: { dropped: number | null; clean: number | null; analysedOfClean: number | null };
  checks: {
    /** fetched - dropped = clean, recomputed from the counts. `ok` is null when unavailable. */
    cleaning: { ok: boolean | null; expectedClean: number | null; actualClean: number | null };
    /** items seen - outside window - duplicates - invalid = fetched. */
    ingest: { ok: boolean | null; expectedFetched: number | null; actualFetched: number | null };
  };
  warnings: "fetch_stopped_early"[];
  /** The last stage the run recorded. */
  reachedStage: StageName | null;
}

function count(run: Run, stage: string, key: string): number | null {
  const value = run.stages.find((s) => s.name === stage)?.counts?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function sum(values: (number | null)[]): number | null {
  return values.some((v) => v === null) ? null : (values as number[]).reduce((a, b) => a + b, 0);
}

function fraction(part: number | null, whole: number | null): number | null {
  return part === null || whole === null || whole <= 0 ? null : part / whole;
}

/** Every value the run did not record is null; nothing here divides by zero or yields NaN. */
export function computeFunnel(run: Run, minReviews: number): Funnel {
  const fetched = count(run, "ingest", "fetched") ?? count(run, "sanitize", "fetched");
  const itemsSeen = count(run, "ingest", "items_seen");
  const outsideWindow = count(run, "ingest", "outside_window");
  const dropped = {
    short: count(run, "sanitize", "dropped_short"),
    nonEnglish: count(run, "sanitize", "dropped_non_english"),
    duplicate: count(run, "sanitize", "dropped_duplicate"),
    invalid: count(run, "sanitize", "dropped_invalid"),
    total: null as number | null,
  };
  dropped.total = sum([dropped.short, dropped.nonEnglish, dropped.duplicate, dropped.invalid]);
  const clean = count(run, "sanitize", "clean");
  const analysed = count(run, "sanitize", "analysed");

  const expectedClean = fetched !== null && dropped.total !== null ? fetched - dropped.total : null;
  const ingestDropped = sum([outsideWindow, count(run, "ingest", "duplicates"), count(run, "ingest", "invalid")]);
  const expectedFetched = itemsSeen !== null && ingestDropped !== null ? itemsSeen - ingestDropped : null;
  const ingestFetched = count(run, "ingest", "fetched");

  const truncated = count(run, "ingest", "truncated");
  const startReached = count(run, "ingest", "window_start_reached");
  const stoppedEarly = (truncated !== null && truncated > 0) || startReached === 0;

  const last = run.stages.filter((s) => (STAGE_NAMES as readonly string[]).includes(s.name)).at(-1);

  return {
    fetched,
    pages: count(run, "ingest", "pages"),
    itemsSeen,
    outsideWindow,
    dropped,
    clean,
    analysed,
    sampled: clean !== null && analysed !== null && analysed < clean,
    marginOverMin: clean === null ? null : clean - minReviews,
    pct: {
      dropped: fraction(dropped.total, fetched),
      clean: fraction(clean, fetched),
      analysedOfClean: fraction(analysed, clean),
    },
    checks: {
      cleaning: {
        ok: expectedClean === null || clean === null ? null : expectedClean === clean,
        expectedClean,
        actualClean: clean,
      },
      ingest: {
        ok: expectedFetched === null || ingestFetched === null ? null : expectedFetched === ingestFetched,
        expectedFetched,
        actualFetched: ingestFetched,
      },
    },
    warnings: stoppedEarly ? ["fetch_stopped_early"] : [],
    reachedStage: (last?.name as StageName | undefined) ?? null,
  };
}
