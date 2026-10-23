import { ExternalLink } from "lucide-react";
import { Fragment, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { RunSummary } from "../../api/types";
import { Card } from "../../components/Card";
import { CopyButton } from "../../components/CopyButton";
import { Mono } from "../../components/Mono";
import { StartTime } from "../../components/StartTime";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDuration, formatInt } from "../../lib/format";

const PAGE_SIZE = 25;

type Tab = "all" | "completed" | "dryrun" | "failed" | "partial" | "other";

const TABS: { id: Tab; label: string; match: (r: RunSummary) => boolean }[] = [
  { id: "all", label: "All", match: () => true },
  { id: "completed", label: "Completed", match: (r) => r.status === "completed" && !r.is_dry_run },
  { id: "dryrun", label: "Dry run", match: (r) => r.is_dry_run },
  { id: "failed", label: "Failed", match: (r) => r.status === "failed" || r.status === "failed_validation" },
  { id: "partial", label: "Partial", match: (r) => r.status === "partial" },
  {
    id: "other",
    label: "Other",
    match: (r) =>
      !["completed", "failed", "failed_validation", "partial"].includes(r.status),
  },
];

const Dash = () => <span className="text-on-surface-variant">—</span>;

/** The model step did not finish, so `analysed` is the sample that was drawn, not reviews read. */
const failedBeforeModel = (r: RunSummary) => r.status === "failed" || r.status === "failed_validation";

function Counts({ run }: { run: RunSummary }) {
  if (run.fetched === null && run.clean === null && run.analysed === null) return <Dash />;
  const muted = failedBeforeModel(run);
  return (
    <span className="whitespace-nowrap">
      {formatInt(run.fetched)} / {formatInt(run.clean)} /{" "}
      {muted && run.analysed !== null ? (
        <span
          title="Sampled; model step failed"
          aria-label={`${formatInt(run.analysed)} analysed (sampled; model step failed)`}
          className="text-on-surface-variant"
        >
          {formatInt(run.analysed)}
        </span>
      ) : (
        formatInt(run.analysed)
      )}
    </span>
  );
}

function RunRow({ run }: { run: RunSummary }) {
  const resume = `python -m pulse run --resume ${run.run_id}`;
  return (
    <tr className="align-top">
      <td className="py-space-sm pr-space-md">
        <span className="flex flex-wrap items-center gap-space-xs">
          <Mono>{run.run_id}</Mono>
          <CopyButton text={run.run_id} label="Copy" ariaLabel={`Copy ${run.run_id}`} />
        </span>
      </td>
      <td className="py-space-sm pr-space-md">
        <StatusBadge status={run.status} run={run} short />
        {run.status === "partial" && (
          <div className="mt-space-xs flex flex-wrap items-center gap-space-xs">
            <Mono className="rounded bg-surface-container px-space-sm py-space-xs">{resume}</Mono>
            <CopyButton text={resume} label="Copy" ariaLabel="Copy resume command" />
          </div>
        )}
      </td>
      <td className="py-space-sm pr-space-md">{run.started_at ? <StartTime iso={run.started_at} /> : <Dash />}</td>
      <td className="py-space-sm pr-space-md whitespace-nowrap">
        {run.duration_s === null ? <Dash /> : formatDuration(run.duration_s)}
      </td>
      <td className="py-space-sm pr-space-md">
        <Counts run={run} />
      </td>
      <td className="py-space-sm pr-space-md">{run.word_count ? formatInt(run.word_count) : <Dash />}</td>
      <td className="py-space-sm pr-space-md">
        {run.doc_url ? (
          <a
            href={run.doc_url}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-space-xs text-primary underline"
          >
            <ExternalLink size={14} aria-hidden="true" />
            Open doc
          </a>
        ) : (
          <Dash />
        )}
      </td>
      <td className="py-space-sm pr-space-md">{run.draft_id ? <Mono>{run.draft_id}</Mono> : <Dash />}</td>
      <td className="py-space-sm">
        <Link to={`/runs/${run.run_id}`} className="text-primary underline">
          View detail
        </Link>
      </td>
    </tr>
  );
}

const FIELD =
  "rounded-lg border border-outline-variant bg-surface-container-lowest px-space-sm py-space-sm text-body-md font-normal";

/** Every run folder, newest first, grouped by week. Read-only: nothing here starts or resumes a run. */
export function RunsTable({ runs }: { runs: RunSummary[] }) {
  const [tab, setTab] = useState<Tab>("all");
  const [week, setWeek] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => setPage(1), [tab, week, search]);

  const weeks = useMemo(
    () => [...new Set(runs.map((r) => r.week_label).filter((w): w is string => !!w))].sort().reverse(),
    [runs],
  );
  const needle = search.trim().toLowerCase();
  const matching = runs.filter(
    (r) =>
      TABS.find((t) => t.id === tab)!.match(r) &&
      (!week || r.week_label === week) &&
      (!needle || r.run_id.toLowerCase().includes(needle) || (r.week_label ?? "").toLowerCase().includes(needle)),
  );
  const pages = Math.max(1, Math.ceil(matching.length / PAGE_SIZE));
  const visible = matching.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const groups: { week: string; runs: RunSummary[] }[] = [];
  for (const run of visible) {
    const key = run.week_label ?? "No week";
    const group = groups.find((g) => g.week === key);
    if (group) group.runs.push(run);
    else groups.push({ week: key, runs: [run] });
  }
  const weekTotal = (key: string) =>
    matching.filter((r) => (r.week_label ?? "No week") === key).length;

  return (
    <Card title="All runs" eyebrow="Newest first" className="mb-space-lg">
      <div role="tablist" aria-label="Filter by status" className="mb-space-md flex flex-wrap gap-space-xs">
        {TABS.map((t) => {
          const selected = t.id === tab;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setTab(t.id)}
              className={`rounded-full border px-space-md py-space-xs text-label-md ${
                selected
                  ? "border-primary bg-surface-container-high font-semibold text-primary"
                  : "border-outline-variant text-on-surface-variant hover:bg-surface-container-low"
              }`}
            >
              {t.label} ({runs.filter(t.match).length})
            </button>
          );
        })}
      </div>

      <div className="mb-space-md flex flex-wrap items-end gap-space-md">
        <label className="flex flex-col gap-space-xs text-label-md">
          Week
          <select value={week} onChange={(e) => setWeek(e.target.value)} className={FIELD}>
            <option value="">All weeks</option>
            {weeks.map((w) => (
              <option key={w} value={w}>
                {w}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-[14rem] flex-1 flex-col gap-space-xs text-label-md">
          Search run id or week
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} className={FIELD} />
        </label>
      </div>

      {matching.length === 0 ? (
        <p className="text-on-surface-variant">No runs match</p>
      ) : (
        <div className="overflow-x-auto">
          <table aria-label="Runs" className="w-full min-w-[64rem] text-left text-body-sm">
            <thead>
              <tr className="text-label-md text-on-surface-variant">
                {["Run id", "Status", "Started", "Duration", "Fetched / clean / analysed", "Words", "Doc", "Draft id", ""].map((h, i) => (
                  <th key={i} scope="col" className="border-b border-outline-variant py-space-sm pr-space-md">
                    {h || <span className="sr-only">Detail</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <Fragment key={group.week}>
                  <tr className="bg-surface-container-low">
                    <th scope="row" className="py-space-sm pl-space-sm pr-space-md text-left font-label-lg text-label-lg">
                      {group.week}
                    </th>
                    <td colSpan={8} className="py-space-sm text-on-surface-variant">
                      {weekTotal(group.week)} {weekTotal(group.week) === 1 ? "run" : "runs"} this week
                    </td>
                  </tr>
                  {group.runs.map((run) => (
                    <RunRow key={run.run_id} run={run} />
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pages > 1 && (
        <nav aria-label="Run pages" className="mt-space-md flex items-center justify-end gap-space-sm">
          <button
            type="button"
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-lg border border-outline-variant px-space-md py-space-xs text-label-md disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-label-md">
            Page {page} of {pages}
          </span>
          <button
            type="button"
            aria-label="Next page"
            disabled={page >= pages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-outline-variant px-space-md py-space-xs text-label-md disabled:opacity-40"
          >
            Next
          </button>
        </nav>
      )}
    </Card>
  );
}
