import { Star } from "lucide-react";

/** Filled stars plus the number: the rating is never conveyed by the stars alone. */
export function Stars({ value, max = 5 }: { value: number; max?: number }) {
  const filled = Math.round(value);
  const text = value.toFixed(1);
  return (
    <span
      role="img"
      aria-label={`${text} out of ${max}`}
      className="inline-flex items-center gap-space-xs"
    >
      <span className="inline-flex" aria-hidden="true">
        {Array.from({ length: max }, (_, i) => (
          <Star
            key={i}
            size={14}
            data-filled={i < filled}
            className={i < filled ? "fill-primary-container text-primary-container" : "text-outline"}
          />
        ))}
      </span>
      <span aria-hidden="true" className="text-label-md text-on-surface">
        {text}
      </span>
    </span>
  );
}
