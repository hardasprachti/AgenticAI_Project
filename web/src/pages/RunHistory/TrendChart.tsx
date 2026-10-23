import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RunSummary } from "../../api/types";
import { Card } from "../../components/Card";
import { ChartFrame } from "../../components/ChartFrame";
import { formatInt, formatIstShort } from "../../lib/format";

const FETCHED = "var(--series-volume)";
const CLEAN = "var(--series-recency)";
const ANALYSED = "var(--series-severity)";
const WORDS = "var(--color-on-surface-variant)";

/**
 * One point per completed run, oldest to newest. Fetched and clean are bars and analysed a line on
 * the left axis; the note's word count is a dashed line on the right axis because it is a different
 * unit. Every number is also in the table view.
 */
export function TrendChart({ runs }: { runs: RunSummary[] }) {
  const completed = runs
    .filter((r) => r.status === "completed" && r.started_at)
    .sort((a, b) => (a.started_at as string).localeCompare(b.started_at as string));

  if (completed.length === 0) {
    return (
      <Card title="Trend" eyebrow="Completed runs" className="mb-space-lg">
        <p className="text-on-surface-variant">No completed runs yet</p>
      </Card>
    );
  }

  const data = completed.map((r) => ({
    run: r.run_id,
    label: formatIstShort(r.started_at as string),
    fetched: r.fetched,
    clean: r.clean,
    analysed: r.analysed,
    words: r.word_count,
  }));

  return (
    <Card title="Trend" eyebrow="Completed runs" className="mb-space-lg">
      <ChartFrame
        title="Completed runs: fetched, clean, analysed and words"
        sampleNote="Words use the right axis. Times are IST."
        table={{
          columns: ["Started (IST)", "Run", "Fetched", "Clean", "Analysed", "Words"],
          rows: data.map((d) => [
            d.label,
            d.run,
            formatInt(d.fetched),
            formatInt(d.clean),
            formatInt(d.analysed),
            formatInt(d.words),
          ]),
        }}
      >
        <div role="img" aria-label={`Chart of ${data.length} completed runs`} className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 800, height: 320 }}>
            <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
              <CartesianGrid stroke="var(--color-outline-variant)" strokeOpacity={0.5} vertical={false} />
              <XAxis dataKey="label" tick={{ fill: "var(--color-on-surface-variant)", fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fill: "var(--color-on-surface-variant)", fontSize: 11 }} />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fill: "var(--color-on-surface-variant)", fontSize: 11 }}
              />
              <Tooltip />
              <Legend />
              <Bar yAxisId="left" dataKey="fetched" name="Fetched" fill={FETCHED} maxBarSize={18} radius={[4, 4, 0, 0]} />
              <Bar yAxisId="left" dataKey="clean" name="Clean" fill={CLEAN} maxBarSize={18} radius={[4, 4, 0, 0]} />
              <Line yAxisId="left" type="monotone" dataKey="analysed" name="Analysed" stroke={ANALYSED} strokeWidth={2} dot={{ r: 4 }} />
              <Line yAxisId="right" type="monotone" dataKey="words" name="Words (right axis)" stroke={WORDS} strokeWidth={2} strokeDasharray="6 4" dot={{ r: 4 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </ChartFrame>
    </Card>
  );
}
