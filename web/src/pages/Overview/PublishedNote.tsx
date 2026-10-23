import { Card } from "../../components/Card";
import { CopyButton } from "../../components/CopyButton";
import { DataUnavailable } from "../../components/DataUnavailable";
import { formatInt } from "../../lib/format";

/** The note exactly as `note.txt` holds it, with the word count against the configured limit. */
export function PublishedNote({
  note,
  wordCount,
  maxWords,
  dryRun,
}: {
  note: string | null;
  wordCount: number;
  maxWords: number;
  dryRun: boolean;
}) {
  const over = wordCount > maxWords;
  const fill = maxWords > 0 ? Math.min(wordCount / maxWords, 1) * 100 : 0;
  return (
    <Card
      title="The note"
      eyebrow={dryRun ? "What would be published (dry run)" : "What was published"}
      className="mb-space-lg"
    >
      {note === null ? (
        <DataUnavailable what="Published note" />
      ) : (
        <>
          <div className="mb-space-md flex flex-wrap items-center justify-between gap-space-md">
            <div className="min-w-[14rem] flex-1">
              <p className="text-label-lg">
                {formatInt(wordCount)} / {formatInt(maxWords)} words
              </p>
              <div
                role="meter"
                aria-label="Word count"
                aria-valuemin={0}
                aria-valuemax={maxWords}
                aria-valuenow={wordCount}
                className="mt-space-xs h-2 overflow-hidden rounded-full bg-surface-container"
              >
                <div
                  className={`h-full rounded-full ${over ? "bg-status-failed-fg" : "bg-primary-container"}`}
                  style={{ width: `${fill}%` }}
                />
              </div>
              {over && (
                <p className="mt-space-xs text-label-md text-status-failed-fg">
                  Over the limit by {formatInt(wordCount - maxWords)} words
                </p>
              )}
            </div>
            <CopyButton text={note} label="Copy note" />
          </div>
          <pre
            data-testid="note-text"
            tabIndex={0}
            className="m-0 overflow-x-auto whitespace-pre-wrap rounded-lg bg-surface-container-low p-space-md font-data-code text-data-code text-on-surface"
          >
            {note}
          </pre>
        </>
      )}
    </Card>
  );
}
