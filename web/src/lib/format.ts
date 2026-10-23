/** Display formatting. Pure; nothing here touches the locale or the browser's time zone. */

const DASH = "—";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MS_PER_DAY = 86_400_000;
const IST_OFFSET_MS = 5.5 * 3_600_000;

const pad = (n: number) => String(n).padStart(2, "0");

/** `10,332`; a dash for null or non-finite. */
export function formatInt(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return DASH;
  return Math.round(n).toLocaleString("en-US");
}

/** Takes a fraction (0.088 -> `8.8%`). At most `digits` decimals, a trailing `.0` is dropped. */
export function formatPercent(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return DASH;
  const text = (x * 100).toFixed(digits);
  return `${digits > 0 ? text.replace(/\.?0+$/, "") : text}%`;
}

function parseDate(iso: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return null;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return Number.isNaN(date.getTime()) ? null : date;
}

/** `13 Aug - 22 Oct 2026`, or with both years when the window crosses a year. */
export function formatWindow(start: string, end: string): string {
  const from = parseDate(start);
  const to = parseDate(end);
  if (!from || !to) return DASH;
  const day = (d: Date) => `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  const fromText =
    from.getUTCFullYear() === to.getUTCFullYear()
      ? day(from)
      : `${day(from)} ${from.getUTCFullYear()}`;
  return `${fromText} - ${day(to)} ${to.getUTCFullYear()}`;
}

/** Whole weeks between two dates (70 days -> 10); NaN if either date is unreadable. */
export function windowWeeks(start: string, end: string): number {
  const from = parseDate(start);
  const to = parseDate(end);
  if (!from || !to) return NaN;
  return Math.round((to.getTime() - from.getTime()) / MS_PER_DAY / 7);
}

/** `7m 16s`, `1m 12s`, `4s`, `1h 2m`. */
export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return DASH;
  const total = Math.round(seconds);
  if (total < 60) return `${total}s`;
  if (total < 3600) return `${Math.floor(total / 60)}m ${total % 60}s`;
  return `${Math.floor(total / 3600)}h ${Math.floor((total % 3600) / 60)}m`;
}

/** The instant in IST (for reading) and UTC (for the tooltip). */
export function formatIst(iso: string): { ist: string; utc: string } {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) return { ist: DASH, utc: DASH };
  const clock = (d: Date) => `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
  const ist = new Date(instant.getTime() + IST_OFFSET_MS);
  return {
    ist: `${ist.getUTCDate()} ${MONTHS[ist.getUTCMonth()]} ${ist.getUTCFullYear()}, ${clock(ist)} IST`,
    utc: `${instant.getUTCFullYear()}-${pad(instant.getUTCMonth() + 1)}-${pad(instant.getUTCDate())} ${clock(instant)} UTC`,
  };
}

const ID_HEAD = 6;
const ID_TAIL = 7;

/** `209a6622a2916a18` -> `209a66…2916a18`. Ids too short to be worth truncating are left alone. */
export function truncateId(id: string): string {
  if (id.length <= ID_HEAD + ID_TAIL + 1) return id;
  return `${id.slice(0, ID_HEAD)}…${id.slice(-ID_TAIL)}`;
}

/** ISO week label (`2026-W43`) of a `YYYY-MM-DD` date: the same week the backend files a run under. */
export function isoWeekLabel(isoDate: string): string {
  const date = parseDate(isoDate);
  if (!date) return DASH;
  // The ISO week belongs to the year of its Thursday.
  const thursday = new Date(date.getTime() + (3 - ((date.getUTCDay() + 6) % 7)) * MS_PER_DAY);
  const yearStart = Date.UTC(thursday.getUTCFullYear(), 0, 1);
  const week = Math.floor((thursday.getTime() - yearStart) / MS_PER_DAY / 7) + 1;
  return `${thursday.getUTCFullYear()}-W${pad(week)}`;
}

/** `10 Aug 2026`. */
export function formatDay(isoDate: string): string {
  const d = parseDate(isoDate);
  return d ? `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}` : DASH;
}

/** `22 Oct 17:45` in IST: a compact label for chart axes. */
export function formatIstShort(iso: string): string {
  const { ist } = formatIst(iso);
  const match = /^(\d+ \w+) \d{4}, (\d{2}:\d{2})/.exec(ist);
  return match ? `${match[1]} ${match[2]}` : ist;
}
