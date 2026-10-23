import { useId, useRef } from "react";
import { Modal } from "./Modal";

/**
 * The only way a real (non-dry) run is started. It says exactly what will happen, including that
 * nothing is emailed, and focuses Cancel first so Enter never publishes by accident.
 */
export function ConfirmPublishDialog({
  week,
  pending = false,
  onConfirm,
  onCancel,
}: {
  week: string;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  const descriptionId = useId();
  const cancel = useRef<HTMLButtonElement>(null);
  return (
    <Modal
      role="alertdialog"
      labelledBy={titleId}
      describedBy={descriptionId}
      onClose={onCancel}
      initialFocus={cancel}
      width="max-w-md"
    >
      <h2 id={titleId} className="font-headline-md text-headline-md">
        Publish week {week}?
      </h2>
      <p id={descriptionId} className="mt-space-sm text-body-md text-on-surface-variant">
        This appends a section to the Google Doc and creates a Gmail draft. Nothing is emailed: the
        draft stays in Drafts until someone sends it.
      </p>
      <div className="mt-space-lg flex justify-end gap-space-sm">
        <button
          ref={cancel}
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-outline-variant px-space-md py-space-sm text-label-lg hover:bg-surface-container-low"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={onConfirm}
          className="rounded-lg bg-primary-container px-space-md py-space-sm text-label-lg text-on-primary-container hover:opacity-90 disabled:opacity-50"
        >
          Publish week {week}
        </button>
      </div>
    </Modal>
  );
}
