import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import type { ConfigView, Run } from "../../api/types";
import { Card } from "../../components/Card";
import { CopyButton } from "../../components/CopyButton";
import { Mono } from "../../components/Mono";
import { formatInt } from "../../lib/format";
import { isDryRun } from "../../lib/status";

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-outline-variant p-space-md">
      <h3 className="mb-space-sm font-label-lg text-label-lg">{title}</h3>
      <div className="flex flex-col gap-space-xs text-body-md">{children}</div>
    </div>
  );
}

function charactersAppended(run: Run): number | null {
  const value = run.stages.find((s) => s.name === "publish_doc")?.counts.characters_appended;
  return typeof value === "number" ? value : null;
}

/** Where the week went: the Google Doc and the Gmail draft. A draft is never sent from here. */
export function PublishingStatus({ run, config }: { run: Run; config: ConfigView }) {
  const dry = isDryRun(run);
  const nothing = run.status === "failed" || run.status === "failed_validation";
  const partial = run.status === "partial";
  const published = run.status === "completed" && !dry;
  const resume = `python -m pulse run --resume ${run.run_id}`;
  const chars = charactersAppended(run);

  return (
    <Card title="Publishing status" eyebrow="Google Doc and Gmail draft" className="mb-space-lg">
      {nothing && <p className="text-body-md">Nothing published</p>}

      {dry && (
        <div className="grid grid-cols-1 gap-space-md md:grid-cols-2">
          <Block title="Google Doc">
            <p>Not published (dry run)</p>
          </Block>
          <Block title="Gmail draft">
            <p>Not published (dry run)</p>
          </Block>
        </div>
      )}

      {(published || partial) && (
        <div className="grid grid-cols-1 gap-space-md md:grid-cols-2">
          <Block title="Google Doc">
            {run.doc_url && (
              <a
                href={run.doc_url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-space-xs text-primary underline"
              >
                <ExternalLink size={14} aria-hidden="true" />
                View in Google Doc
              </a>
            )}
            <p>Section appended: Yes</p>
            {run.doc_revision_id && (
              <p>
                Revision <Mono>{run.doc_revision_id}</Mono>
              </p>
            )}
            {chars !== null && <p>{formatInt(chars)} characters appended</p>}
          </Block>

          <Block title="Gmail draft">
            {published ? (
              <>
                {run.draft_id && (
                  <p>
                    Draft <Mono>{run.draft_id}</Mono>
                  </p>
                )}
                <p>To: {config.draft_to ?? "—"}</p>
                <p>Subject: Groww Weekly Review Pulse - {run.week_label}</p>
                <p className="font-label-lg text-label-lg">Draft only - never sent</p>
              </>
            ) : (
              <>
                <p className="font-label-lg text-label-lg text-status-failed-fg">Failed</p>
                <p>The draft was not created. Finish it from a terminal:</p>
                <p className="flex flex-wrap items-center gap-space-sm">
                  <Mono className="rounded bg-surface-container px-space-sm py-space-xs">{resume}</Mono>
                  <CopyButton text={resume} label="Copy command" />
                </p>
              </>
            )}
          </Block>
        </div>
      )}
    </Card>
  );
}
