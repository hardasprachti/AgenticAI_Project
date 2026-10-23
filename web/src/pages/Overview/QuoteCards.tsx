import { useState } from "react";
import type { Pulse, PulseQuote } from "../../api/types";
import { Mono } from "../../components/Mono";
import { ReviewDrawer } from "../../components/ReviewDrawer";
import { Stars } from "../../components/Stars";
import { ThemeChip } from "../../components/ThemeChip";
import { truncateId } from "../../lib/format";

export function QuoteCards({ pulse, runId }: { pulse: Pulse; runId: string }) {
  const [open, setOpen] = useState<PulseQuote | null>(null);
  const labels = Object.fromEntries(pulse.themes.map((t) => [t.theme_id, t.label]));
  return (
    <section aria-labelledby="user-quotes" className="mb-space-lg">
      <h2 id="user-quotes" className="mb-space-md font-headline-lg text-headline-lg">
        What users said
      </h2>
      <ul className="m-0 grid list-none grid-cols-1 gap-space-md p-0 lg:grid-cols-3">
        {pulse.quotes.map((quote) => (
          <li
            key={quote.review_id}
            className="flex flex-col gap-space-sm rounded-xl border border-outline-variant bg-surface-container-lowest p-space-lg"
          >
            <blockquote className="m-0 text-body-lg text-on-surface">"{quote.text}"</blockquote>
            <div className="flex flex-wrap items-center gap-space-sm">
              <Stars value={quote.rating} />
              <ThemeChip
                themeId={quote.theme_id}
                label={labels[quote.theme_id] ?? quote.theme_id}
              />
            </div>
            <div className="mt-auto flex items-center justify-between gap-space-sm">
              <Mono className="text-on-surface-variant">{truncateId(quote.review_id)}</Mono>
              <button
                type="button"
                onClick={() => setOpen(quote)}
                aria-label={`Open source review ${truncateId(quote.review_id)}`}
                className="rounded-lg border border-outline-variant px-space-sm py-space-xs text-label-md text-primary hover:bg-surface-container-low"
              >
                Source review
              </button>
            </div>
          </li>
        ))}
      </ul>
      {open && (
        <ReviewDrawer
          runId={runId}
          reviewId={open.review_id}
          quote={open.text}
          themeLabels={labels}
          onClose={() => setOpen(null)}
        />
      )}
    </section>
  );
}
