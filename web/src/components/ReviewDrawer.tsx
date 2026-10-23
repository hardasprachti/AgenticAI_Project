import { X } from "lucide-react";
import { useId } from "react";
import { useReviews } from "../api/hooks";
import { findQuoteRange } from "../lib/highlight";
import { truncateId } from "../lib/format";
import { DataUnavailable } from "./DataUnavailable";
import { Mono } from "./Mono";
import { Modal } from "./Modal";
import { Stars } from "./Stars";
import { ThemeChip } from "./ThemeChip";

function Highlighted({ text, quote }: { text: string; quote: string }) {
  const range = findQuoteRange(text, quote);
  if (!range) return <>{text}</>;
  return (
    <>
      {text.slice(0, range[0])}
      <mark className="rounded bg-primary-fixed px-0.5 text-on-primary-fixed">
        {text.slice(range[0], range[1])}
      </mark>
      {text.slice(range[1])}
    </>
  );
}

/**
 * The review a quote came from: rating, date, app version, theme, title and the full text with
 * the quote marked. That is everything the analysed set holds; there is no reviewer or device.
 */
export function ReviewDrawer({
  runId,
  reviewId,
  quote,
  themeLabels,
  onClose,
}: {
  runId: string;
  reviewId: string;
  quote: string;
  themeLabels: Record<string, string>;
  onClose: () => void;
}) {
  const titleId = useId();
  const reviews = useReviews(runId, { review_id: [reviewId] });
  const review = reviews.data?.items[0];
  return (
    <Modal labelledBy={titleId} onClose={onClose} placement="right" width="max-w-md">
      <div className="mb-space-md flex items-start justify-between gap-space-md">
        <div>
          <h2 id={titleId} className="font-headline-md text-headline-md">
            Source review
          </h2>
          <Mono className="text-on-surface-variant">{truncateId(reviewId)}</Mono>
        </div>
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-surface-container"
        >
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {reviews.isPending && <p role="status">Loading the review…</p>}
      {reviews.isError && <DataUnavailable what="Source review" />}
      {reviews.data && !review && <p>Source review not in the analysed set</p>}
      {review && (
        <div className="flex flex-col gap-space-md">
          <div className="flex flex-wrap items-center gap-space-md">
            {review.rating !== null && <Stars value={review.rating} />}
            {review.theme_id && (
              <ThemeChip
                themeId={review.theme_id}
                label={themeLabels[review.theme_id] ?? review.theme_id}
              />
            )}
          </div>
          <dl className="m-0 grid grid-cols-2 gap-space-md text-body-md">
            <div>
              <dt className="text-label-sm uppercase text-on-surface-variant">Date</dt>
              <dd className="m-0">{review.date ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-label-sm uppercase text-on-surface-variant">App version</dt>
              <dd className="m-0">{review.app_version ?? "—"}</dd>
            </div>
          </dl>
          {review.title && <p className="font-label-lg text-label-lg">{review.title}</p>}
          <p className="whitespace-pre-wrap text-body-lg">
            <Highlighted text={review.text} quote={quote} />
          </p>
        </div>
      )}
    </Modal>
  );
}
