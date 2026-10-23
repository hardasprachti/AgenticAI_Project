import type { Pulse } from "../../api/types";
import { ThemeChip } from "../../components/ThemeChip";

/** Actions are `{text, theme_id}` and nothing more: no owner, impact or size is invented. */
export function ActionCards({ pulse }: { pulse: Pulse }) {
  const labels = Object.fromEntries(pulse.themes.map((t) => [t.theme_id, t.label]));
  return (
    <section aria-labelledby="action-ideas" className="mb-space-lg">
      <h2 id="action-ideas" className="mb-space-md font-headline-lg text-headline-lg">
        Action ideas
      </h2>
      <ol className="m-0 grid list-none grid-cols-1 gap-space-md p-0 lg:grid-cols-3">
        {pulse.actions.map((action, index) => (
          <li
            key={index}
            className="flex gap-space-md rounded-xl border border-outline-variant bg-surface-container-lowest p-space-lg"
          >
            <span
              aria-hidden="true"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-container text-label-md text-on-primary-container"
            >
              {index + 1}
            </span>
            <div className="flex flex-col gap-space-sm">
              <p className="text-body-md">{action.text}</p>
              <div>
                <ThemeChip
                  themeId={action.theme_id}
                  label={labels[action.theme_id] ?? action.theme_id}
                />
              </div>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
