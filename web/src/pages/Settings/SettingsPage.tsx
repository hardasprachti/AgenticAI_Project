import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import { useConfig } from "../../api/hooks";
import { Card } from "../../components/Card";
import { DataUnavailable } from "../../components/DataUnavailable";
import { Mono } from "../../components/Mono";

function Facts({ children }: { children: ReactNode }) {
  return <dl className="m-0 grid grid-cols-1 gap-x-space-lg gap-y-space-sm md:grid-cols-[14rem_1fr]">{children}</dl>;
}

function Fact({ label, id, children }: { label: string; id?: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-label-lg text-on-surface-variant">{label}</dt>
      <dd data-testid={id} className="m-0 text-body-md">
        {children}
      </dd>
    </>
  );
}

/** The settings the dashboard reads, as plain text. Nothing here can be changed from the browser. */
export function SettingsPage() {
  const config = useConfig();
  const c = config.data;
  return (
    <div>
      <header className="mb-space-lg">
        <h1 className="font-headline-xl text-headline-xl">Settings</h1>
        <p className="mt-space-xs text-body-md text-on-surface-variant">
          Read from config.yaml. Edit that file to change a value. This page never shows secrets or
          file paths.
        </p>
      </header>

      {config.isPending && <p role="status">Loading settings…</p>}
      {config.isError && <DataUnavailable what="Settings" />}

      {c && (
        <div className="flex flex-col gap-space-lg">
          <Card title="Source">
            <Facts>
              <Fact label="App package">
                <Mono>{c.app.play_package}</Mono>
              </Fact>
              <Fact label="Language / country">
                {c.app.play_lang} / {c.app.play_country}
              </Fact>
              <Fact label="Review window">{c.window_weeks} weeks</Fact>
            </Facts>
          </Card>

          <Card title="Themes and ranking">
            <Facts>
              <Fact label="Maximum themes" id="max-themes">
                {c.max_themes}
              </Fact>
              <Fact label="Taxonomy">
                <ul className="m-0 list-disc pl-space-lg">
                  {c.taxonomy.map((label) => (
                    <li key={label}>{label}</li>
                  ))}
                </ul>
              </Fact>
              <Fact label="Ranking weights" id="weights">
                volume {c.ranking.weights.volume} · recency {c.ranking.weights.recency} · severity{" "}
                {c.ranking.weights.severity}
              </Fact>
              <Fact label="Recency window" id="recency-window">
                {c.ranking.recency_window_weeks} weeks
              </Fact>
            </Facts>
          </Card>

          <Card title="The note">
            <Facts>
              <Fact label="Maximum words" id="max-words">
                {c.pulse.max_words}
              </Fact>
              <Fact label="Minimum reviews" id="min-reviews">
                {c.pulse.min_reviews}
              </Fact>
              <Fact label="Minimum words per review" id="min-words">
                {c.pulse.min_words}
              </Fact>
              <Fact label="Maximum analysed" id="max-analysed">
                {c.pulse.max_analysed}
              </Fact>
            </Facts>
          </Card>

          <Card title="Models" eyebrow="Configured now, not recorded per run">
            <Facts>
              <Fact label="Theme assignment">
                <Mono>{c.models.theme_assign ?? "—"}</Mono>
              </Fact>
              <Fact label="Compose">
                <Mono>{c.models.compose ?? "—"}</Mono>
              </Fact>
              <Fact label="Judge">
                <Mono>{c.models.judge ?? "—"}</Mono>
              </Fact>
              <Fact label="Batch size" id="batch-size">
                {c.batch_size}
              </Fact>
            </Facts>
          </Card>

          <Card title="Delivery">
            <Facts>
              <Fact label="Draft recipient" id="draft-to">
                {c.draft_to ?? "—"}
              </Fact>
              <Fact label="Google Doc">
                {c.doc_url ? (
                  <a
                    href={c.doc_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-space-xs text-primary underline"
                  >
                    <ExternalLink size={14} aria-hidden="true" />
                    Open Google Doc
                  </a>
                ) : (
                  "—"
                )}
              </Fact>
            </Facts>
          </Card>
        </div>
      )}
    </div>
  );
}
