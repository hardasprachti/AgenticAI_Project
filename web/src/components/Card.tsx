import { useId, type ReactNode } from "react";

/** Level 1 surface (DESIGN.md): white, 1px hairline, no shadow. */
export function Card({
  title,
  eyebrow,
  children,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  className?: string;
}) {
  const titleId = useId();
  return (
    <section
      aria-labelledby={titleId}
      className={`rounded-xl border border-outline-variant bg-surface-container-lowest p-space-lg ${className}`.trim()}
    >
      <header className="mb-space-md">
        {eyebrow && <p className="text-label-sm uppercase text-on-surface-variant">{eyebrow}</p>}
        <h2 id={titleId} className="font-headline-md text-headline-md text-on-surface">{title}</h2>
      </header>
      {children}
    </section>
  );
}
