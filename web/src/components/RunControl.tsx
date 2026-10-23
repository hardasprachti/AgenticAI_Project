import { useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { queryKeys, useActive } from "../api/hooks";
import { api, ApiError } from "../api/client";
import type { StartRunBody } from "../api/types";
import { formatDuration, isoWeekLabel } from "../lib/format";
import { ConfirmPublishDialog } from "./ConfirmPublishDialog";
import { Modal } from "./Modal";

const todayIso = () => new Date().toISOString().slice(0, 10);

/** Elapsed seconds, advanced locally between the 5 s polls. */
function useLiveElapsed(elapsed: number | null | undefined, updatedAt: number): number | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (elapsed == null) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [elapsed]);
  if (elapsed == null) return null;
  return elapsed + Math.max(0, now - updatedAt) / 1000;
}

function RunControlDialog({ onClose }: { onClose: () => void }) {
  const titleId = useId();
  const queryClient = useQueryClient();
  const active = useActive();
  const [source, setSource] = useState<"play" | "csv">("play");
  const [asOf, setAsOf] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false); // set synchronously, so a double click cannot slip past state

  const state = active.data;
  const running = state?.active === true;
  const elapsed = useLiveElapsed(state?.elapsed_s, active.dataUpdatedAt);
  const finished = state && !state.active && state.started_by_api && state.exit_code !== null;

  // A finished run changes what the other pages show.
  const newRunId = finished ? state.new_run_id : null;
  useEffect(() => {
    if (!finished) return;
    void queryClient.invalidateQueries({ queryKey: queryKeys.runs });
    void queryClient.invalidateQueries({ queryKey: ["run"] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.ledger });
  }, [finished, newRunId, queryClient]);

  async function start(body: StartRunBody) {
    if (inFlight.current || running) return;
    inFlight.current = true;
    setPending(true);
    setError(null);
    try {
      await api.startRun(body);
      setConfirming(false);
      await queryClient.invalidateQueries({ queryKey: queryKeys.active });
    } catch (err) {
      setConfirming(false);
      setError(
        err instanceof ApiError && err.status === 409
          ? "A run is already in progress"
          : err instanceof Error
            ? err.message
            : "The run could not be started",
      );
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  const body = (publish: boolean): StartRunBody => ({
    source,
    dry_run: !publish,
    ...(publish ? { confirm: "publish" } : {}),
    ...(asOf ? { as_of: asOf } : {}),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (pending || running) return;
    if (dryRun) void start(body(false));
    else setConfirming(true);
  }

  return (
    <>
      <Modal labelledBy={titleId} onClose={onClose}>
        <div className="mb-space-md flex items-start justify-between">
          <h2 id={titleId} className="font-headline-md text-headline-md">
            New run
          </h2>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-surface-container"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-space-md">
          <label className="flex flex-col gap-space-xs text-label-lg">
            Source
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as "play" | "csv")}
              className="rounded-lg border border-outline-variant bg-surface-container-lowest px-space-sm py-space-sm text-body-md font-normal"
            >
              <option value="play">Play Store live</option>
              <option value="csv">CSV fixture</option>
            </select>
          </label>

          <label className="flex flex-col gap-space-xs text-label-lg">
            As of (optional)
            <input
              type="date"
              value={asOf}
              max={todayIso()}
              onChange={(e) => setAsOf(e.target.value)}
              className="rounded-lg border border-outline-variant bg-surface-container-lowest px-space-sm py-space-sm text-body-md font-normal"
            />
          </label>

          <div className="flex items-center justify-between gap-space-md rounded-lg border border-outline-variant p-space-md">
            <div>
              <p id={`${titleId}-dry`} className="text-label-lg">
                Dry run
              </p>
              <p className="text-body-sm text-on-surface-variant">
                On: analyse only, publish nothing. Off: also write to the Google Doc and create a Gmail draft.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={dryRun}
              aria-labelledby={`${titleId}-dry`}
              onClick={() => setDryRun((v) => !v)}
              className={`relative h-6 w-11 shrink-0 rounded-full border border-outline transition-colors ${dryRun ? "bg-primary-container" : "bg-surface-container-high"}`}
            >
              <span
                aria-hidden="true"
                className={`absolute top-0.5 h-4 w-4 rounded-full bg-on-primary-container transition-all ${dryRun ? "left-6" : "left-0.5 !bg-outline"}`}
              />
            </button>
          </div>

          {error && (
            <p role="alert" className="rounded-lg border border-status-failed-border bg-status-failed-bg p-space-sm text-body-md text-status-failed-fg">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-space-sm">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-outline-variant px-space-md py-space-sm text-label-lg hover:bg-surface-container-low"
            >
              Close
            </button>
            <button
              type="submit"
              disabled={pending || running}
              className="rounded-lg bg-primary-container px-space-md py-space-sm text-label-lg text-on-primary-container hover:opacity-90 disabled:opacity-50"
            >
              {dryRun ? "Start dry run" : "Review and publish…"}
            </button>
          </div>
        </form>

        {running && state && (
          <section aria-live="polite" className="mt-space-lg rounded-lg bg-status-running-bg p-space-md text-status-running-fg">
            <p className="text-label-lg">Running for {formatDuration(Math.floor(elapsed ?? 0))}</p>
            <div
              role="progressbar"
              aria-label="Run in progress"
              className="mt-space-sm h-1.5 overflow-hidden rounded-full bg-status-running-border"
            >
              <div className="h-full w-1/3 animate-pulse rounded-full bg-status-running-fg motion-reduce:animate-none" />
            </div>
            <p className="mt-space-sm text-body-sm">Run files appear when the analysis ends (usually 6-8 minutes)</p>
            {state.last_line && <p className="mt-space-xs font-data-code text-data-code">{state.last_line}</p>}
          </section>
        )}

        {finished && state && (
          <section className="mt-space-lg rounded-lg border border-outline-variant p-space-md">
            <p className="text-label-md uppercase text-on-surface-variant">Last run started from this page</p>
            <p className="mt-space-xs text-body-md">{state.exit_message}</p>
            {state.exit_code !== 0 && state.stderr_tail.length > 0 && (
              <pre className="mt-space-sm overflow-x-auto whitespace-pre-wrap rounded bg-surface-container p-space-sm font-data-code text-data-code">
                {state.stderr_tail.join("\n")}
              </pre>
            )}
            {state.new_run_id && (
              <Link
                to={`/runs/${state.new_run_id}`}
                onClick={onClose}
                className="mt-space-sm inline-block text-label-lg text-primary underline"
              >
                Go to run
              </Link>
            )}
          </section>
        )}
      </Modal>

      {confirming && (
        <ConfirmPublishDialog
          week={isoWeekLabel(asOf || todayIso())}
          pending={pending}
          onCancel={() => setConfirming(false)}
          onConfirm={() => void start(body(true))}
        />
      )}
    </>
  );
}

/** Mounted only while open, so every opening starts from the safe defaults (dry run ON). */
export function RunControl({ open, onClose }: { open: boolean; onClose: () => void }) {
  return open ? <RunControlDialog onClose={onClose} /> : null;
}
