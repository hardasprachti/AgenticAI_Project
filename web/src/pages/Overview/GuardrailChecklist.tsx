import { CheckCircle2, MinusCircle, XCircle } from "lucide-react";
import { useId, useMemo } from "react";
import { useReviews } from "../../api/hooks";
import type { ConfigView, Pulse, ReviewRow, Run } from "../../api/types";
import { Card } from "../../components/Card";
import { evaluateGuardrails, tallyGuardrails, type Guardrail } from "../../lib/guardrails";

const STATUS = {
  pass: { text: "Pass", Icon: CheckCircle2, tone: "text-status-completed-fg" },
  fail: { text: "Fail", Icon: XCircle, tone: "text-status-failed-fg" },
  unavailable: { text: "Unavailable", Icon: MinusCircle, tone: "text-on-surface-variant" },
} as const;

function Row({ guardrail }: { guardrail: Guardrail }) {
  const labelId = useId();
  const { text, Icon, tone } = STATUS[guardrail.status];
  return (
    <li
      aria-labelledby={labelId}
      className="flex flex-col gap-space-xs rounded-lg border border-outline-variant p-space-md"
    >
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <span id={labelId} className="font-label-lg text-label-lg">
          {guardrail.label}
        </span>
        <span className={`inline-flex items-center gap-space-xs text-label-md ${tone}`}>
          <Icon size={16} aria-hidden="true" data-status-icon={guardrail.status} />
          {text}
        </span>
      </div>
      <p className="text-body-sm text-on-surface-variant">{guardrail.detail}</p>
      {guardrail.items && (
        <ul className="m-0 flex list-none flex-wrap gap-space-sm p-0">
          {guardrail.items.map((item) => (
            <li
              key={item}
              className="rounded-full bg-surface-container px-space-sm py-space-xxs text-label-md"
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

/**
 * Every row is computed from the run, the pulse and the analysed reviews it quotes. A row whose
 * data is missing says Unavailable and is not counted as a pass.
 */
export function GuardrailChecklist({
  runId,
  run,
  pulse,
  config,
}: {
  runId: string;
  run: Run | null;
  pulse: Pulse | null;
  config: ConfigView;
}) {
  const quoteIds = useMemo(() => pulse?.quotes.map((q) => q.review_id) ?? [], [pulse]);
  const reviews = useReviews(pulse ? runId : undefined, { review_id: quoteIds, page_size: 100 });
  const reviewsById = useMemo<Record<string, ReviewRow> | null>(
    () =>
      reviews.data ? Object.fromEntries(reviews.data.items.map((r) => [r.review_id, r])) : null,
    [reviews.data],
  );
  const guardrails = evaluateGuardrails({ run, pulse, reviewsById, config });
  const tally = tallyGuardrails(guardrails);
  // Until the quoted reviews arrive the quote row is Unavailable; do not show that as a result.
  const checking = pulse !== null && reviews.isPending;
  return (
    <Card title="Guardrails" eyebrow="Checked from the data, not assumed" className="mb-space-lg">
      <p className="mb-space-md font-data-metric text-headline-md" aria-live="polite">
        {checking ? "Checking the source reviews…" : `${tally.pass} / ${tally.total} passed`}
      </p>
      <ul className="m-0 grid list-none grid-cols-1 gap-space-sm p-0 lg:grid-cols-2">
        {guardrails.map((g) => (
          <Row key={g.id} guardrail={g} />
        ))}
      </ul>
    </Card>
  );
}
