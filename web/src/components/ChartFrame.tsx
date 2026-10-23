import { useId, useState, type ReactNode } from "react";

export interface ChartTable {
  columns: string[];
  rows: (string | number)[][];
}

/** A titled chart with a "View as table" toggle, so every chart has a text equivalent. */
export function ChartFrame({
  title,
  sampleNote,
  table,
  children,
}: {
  title: string;
  sampleNote?: string;
  table: ChartTable;
  children: ReactNode;
}) {
  const [asTable, setAsTable] = useState(false);
  const titleId = useId();
  return (
    <figure aria-labelledby={titleId} className="m-0">
      <div className="mb-space-sm flex items-start justify-between gap-space-md">
        <div>
          <figcaption id={titleId} className="font-label-lg text-label-lg text-on-surface">
            {title}
          </figcaption>
          {sampleNote && <p className="text-body-sm text-on-surface-variant">{sampleNote}</p>}
        </div>
        <button
          type="button"
          aria-pressed={asTable}
          onClick={() => setAsTable((v) => !v)}
          className="shrink-0 rounded-lg border border-outline-variant px-space-sm py-space-xs text-label-md text-on-surface hover:bg-surface-container-low aria-pressed:bg-surface-container-high"
        >
          View as table
        </button>
      </div>
      {asTable ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-body-sm">
            <thead>
              <tr>
                {table.columns.map((c) => (
                  <th
                    key={c}
                    scope="col"
                    className="border-b border-outline-variant py-space-xs pr-space-md text-label-md text-on-surface-variant"
                  >
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td
                      key={j}
                      className="border-b border-outline-variant/50 py-space-xs pr-space-md text-on-surface"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        children
      )}
    </figure>
  );
}
