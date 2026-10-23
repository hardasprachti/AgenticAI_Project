import { Check, Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const COPIED_MS = 2000;

/**
 * Copies `text` with the clipboard API. If that is missing or rejects (permissions, insecure
 * origin), shows the text in a field, selected, so the person can press Ctrl+C.
 */
export function CopyButton({
  text,
  label = "Copy",
  ariaLabel,
}: {
  text: string;
  label?: string;
  /** When several copy buttons share a page, a name that says which one. */
  ariaLabel?: string;
}) {
  const [state, setState] = useState<"idle" | "copied" | "manual">("idle");
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const field = useRef<HTMLInputElement>(null);

  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    if (state === "manual") {
      field.current?.focus();
      field.current?.select();
    }
  }, [state]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      setState("manual");
      return;
    }
    setState("copied");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), COPIED_MS);
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-space-sm">
      <button
        type="button"
        onClick={copy}
        aria-label={ariaLabel}
        className="inline-flex items-center gap-space-xs rounded-lg border border-outline-variant px-space-sm py-space-xs text-label-md text-on-surface hover:bg-surface-container-low"
      >
        {state === "copied" ? (
          <Check size={14} aria-hidden="true" />
        ) : (
          <Copy size={14} aria-hidden="true" />
        )}
        {label}
      </button>
      <span role="status" className="text-label-md text-primary">
        {state === "copied" ? "Copied" : ""}
      </span>
      {state === "manual" && (
        <input
          ref={field}
          readOnly
          value={text}
          aria-label="Text to copy"
          onFocus={(e) => e.currentTarget.select()}
          className="min-w-[16rem] rounded border border-outline-variant bg-surface-container-lowest px-space-sm py-space-xs font-data-code text-data-code"
        />
      )}
    </span>
  );
}
