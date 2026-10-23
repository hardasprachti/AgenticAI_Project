/** Stand-in for pages built in later tasks (Overview, Run Detail, History, Ledger, Settings). */
export function Placeholder({ title }: { title: string }) {
  return (
    <section>
      <h1 className="font-headline-xl text-headline-xl">{title}</h1>
      <p className="mt-space-sm text-on-surface-variant">This page is built in a later task.</p>
    </section>
  );
}
