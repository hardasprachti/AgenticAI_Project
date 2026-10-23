import type { ReactNode } from "react";

/** Run ids, review ids and commands: fixed-width so digits line up. */
export function Mono({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`font-data-code text-data-code ${className}`.trim()}>{children}</span>;
}
