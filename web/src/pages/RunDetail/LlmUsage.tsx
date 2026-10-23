import type { ConfigView, Run } from "../../api/types";
import { Card } from "../../components/Card";
import { Mono } from "../../components/Mono";
import { formatInt } from "../../lib/format";

type Task = "theme_assign" | "compose";

/** Calls, tokens and waiting per task. There is no cost estimate: the run does not record one. */
export function LlmUsage({ run, config }: { run: Run; config: ConfigView | undefined }) {
  const tasks = Object.entries(run.llm_usage);
  const totalTokens = tasks.reduce((sum, [, u]) => sum + u.prompt_tokens + u.completion_tokens, 0);
  return (
    <Card title="LLM usage" eyebrow="Model calls: time and tokens" className="mb-space-lg">
      <div>
        {tasks.length === 0 ? (
          <p className="text-on-surface-variant">No model calls were recorded for this run.</p>
        ) : (
          <>
            <p className="mb-space-md text-body-md">
              Total tokens: <span className="font-label-lg text-label-lg">{formatInt(totalTokens)}</span>
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[44rem] text-left text-body-sm">
                <thead>
                  <tr className="text-label-md text-on-surface-variant">
                    {["Task", "Calls", "Prompt tokens", "Completion tokens", "Retries", "Rate-limited", "Invalid replies", "Waited (s)", "Model"].map((h) => (
                      <th key={h} scope="col" className="border-b border-outline-variant py-space-sm pr-space-md">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tasks.map(([task, u]) => (
                    <tr key={task}>
                      <th scope="row" className="py-space-sm pr-space-md text-left font-data-code text-data-code">
                        {task}
                      </th>
                      <td className="py-space-sm pr-space-md">{formatInt(u.calls)}</td>
                      <td className="py-space-sm pr-space-md">{formatInt(u.prompt_tokens)}</td>
                      <td className="py-space-sm pr-space-md">{formatInt(u.completion_tokens)}</td>
                      <td className="py-space-sm pr-space-md">{formatInt(u.retries)}</td>
                      <td className="py-space-sm pr-space-md">{formatInt(u.rate_limited)}</td>
                      <td className="py-space-sm pr-space-md">{formatInt(u.invalid_replies)}</td>
                      <td className="py-space-sm pr-space-md">{formatInt(u.waited_s)}</td>
                      <td className="py-space-sm">
                        <Mono>{config?.models[task as Task] ?? "—"}</Mono>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-space-sm text-body-sm text-on-surface-variant">
              Models: Configured now (not recorded per run).
            </p>
          </>
        )}
        {Object.keys(run.prompt_versions).length > 0 && (
          <p className="mt-space-sm flex flex-wrap gap-x-space-md text-body-sm">
            Prompt versions:
            {Object.entries(run.prompt_versions).map(([task, version]) => (
              <Mono key={task}>{version}</Mono>
            ))}
          </p>
        )}
      </div>
    </Card>
  );
}
