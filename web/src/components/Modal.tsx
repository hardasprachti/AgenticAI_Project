import { useEffect, useRef, type KeyboardEvent, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Modal surface (DESIGN.md Level 3): focus moves in on open, Tab stays inside, Escape closes, and
 * focus returns to where it was. Key events are stopped here so a modal opened from inside another
 * one handles its own Escape and Tab and the one underneath never sees them.
 */
export function Modal({
  role = "dialog",
  labelledBy,
  describedBy,
  onClose,
  initialFocus,
  children,
  width = "max-w-lg",
  placement = "center",
}: {
  role?: "dialog" | "alertdialog";
  labelledBy: string;
  describedBy?: string;
  onClose: () => void;
  initialFocus?: RefObject<HTMLElement>;
  children: ReactNode;
  width?: string;
  /** `right` makes a full-height side drawer. */
  placement?: "center" | "right";
}) {
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const target = initialFocus?.current ?? panel.current?.querySelector<HTMLElement>(FOCUSABLE);
    (target ?? panel.current)?.focus();
    return () => previous?.focus?.();
    // Focus is placed once, when the modal opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onClose();
    } else if (event.key === "Tab") {
      event.stopPropagation();
      const items = [...(panel.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])];
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !panel.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !panel.current?.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    }
  }

  return createPortal(
    <div
      className={
        placement === "right"
          ? "fixed inset-0 z-[80] flex justify-end"
          : "fixed inset-0 z-[80] flex items-center justify-center p-space-md"
      }
    >
      <div className="absolute inset-0 bg-inverse-surface/60" aria-hidden="true" onClick={onClose} />
      <div
        ref={panel}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className={`relative w-full ${width} border border-outline-variant bg-surface-container-lowest p-space-lg shadow-xl ${
          placement === "right" ? "h-full overflow-y-auto" : "rounded-xl"
        }`}
      >
        {children}
      </div>
    </div>,
    document.body,
  );
}
