import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { scrub } from "../../lib/scrub";

const CHART_TOKENS = {
  grid: "var(--color-line)",
  text: "var(--color-grey)",
  navy: "var(--color-navy)",
  blue: "var(--color-blue)",
  blueTint: "var(--color-blue-tint)",
  paper: "var(--color-paper)",
  line: "var(--color-line-2)",
} as const;

const COUNTRY_ALIASES: Record<string, string> = {
  GB: "United Kingdom",
  UK: "United Kingdom",
  "UNITED KINGDOM": "United Kingdom",
  US: "United States",
  USA: "United States",
  "UNITED STATES": "United States",
};

type ChartSize = "compact" | "full";

/** Present a data-value label (classifier tags arrive snake_cased). These are
 *  data values, not locked enum vocabulary — presentation-casing is honest. */
export function humaniseLabel(raw: string): string {
  const clean = scrub(raw).replaceAll("_", " ").trim();
  return clean.length === 0 ? clean : clean[0].toUpperCase() + clean.slice(1);
}

/** Normalise mixed ISO and name geography inputs before chart labels render. */
export function normaliseGeographies(data: Record<string, number>): Record<string, number> {
  return Object.entries(data).reduce<Record<string, number>>((normalised, [rawLabel, count]) => {
    const clean = scrub(rawLabel).trim();
    const label = COUNTRY_ALIASES[clean.toUpperCase()] ?? clean;
    normalised[label] = (normalised[label] ?? 0) + count;
    return normalised;
  }, {});
}

/** Fill the inclusive evidence-year range so a missing year stays visible at zero. */
export function fillYearRange(data: Record<string, number>): Array<{ label: string; count: number }> {
  const years = Object.entries(data).flatMap(([label, count]) => {
    const year = Number(label);
    return /^\d{4}$/.test(label) && Number.isInteger(year) ? [{ year, count }] : [];
  });
  if (years.length === 0) return [];
  const counts = new Map(years.map(({ year, count }) => [year, count]));
  const first = Math.min(...counts.keys());
  const last = Math.max(...counts.keys());
  return Array.from({ length: last - first + 1 }, (_, index) => {
    const year = first + index;
    return { label: String(year), count: counts.get(year) ?? 0 };
  });
}

/** Discovered themes, largest first (owner rule, 2026-07-29). */
export function orderThemes<T extends { size: number }>(themes: T[]): T[] {
  return [...themes].sort((a, b) => b.size - a.size);
}

/** One tooltip style across every landscape chart (token colours, 0 radius). */
function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value?: number | string; payload?: { label?: string } }>;
  label?: string | number;
}) {
  if (!active || payload === undefined || payload.length === 0) return null;
  const row = payload[0];
  const heading = row.payload?.label ?? String(label ?? "");
  return (
    <div className="border border-line-2 bg-paper px-2.5 py-1.5 shadow-sm">
      <p className="text-caption font-semibold text-navy">{heading}</p>
      <p className="text-caption text-grey">
        {row.value} source{row.value === 1 ? "" : "s"}
      </p>
    </div>
  );
}

const TRUNCATE_AT = 24;

function truncateTick(value: string): string {
  return value.length > TRUNCATE_AT ? `${value.slice(0, TRUNCATE_AT - 1)}…` : value;
}

/** Shared horizontal distribution chart for evidence types and publication
 *  geography: descending by count, height scaled to the row count so bars
 *  keep a readable weight, full label on hover. */
export function EvidenceDistributionChart({
  data,
  size = "full",
}: {
  data: Record<string, number>;
  size?: ChartSize;
}) {
  const rows = Object.entries(data)
    .map(([label, count]) => ({ label: humaniseLabel(label), count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);
  if (rows.length === 0) return null;
  const rowHeight = size === "compact" ? 26 : 30;
  return (
    <div className="min-w-0" style={{ height: rows.length * rowHeight + 36 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 24, top: 4 }}>
          <CartesianGrid horizontal={false} stroke={CHART_TOKENS.grid} />
          <XAxis
            type="number"
            allowDecimals={false}
            tick={{ fontSize: 11, fill: CHART_TOKENS.text }}
            axisLine={{ stroke: CHART_TOKENS.grid }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={size === "compact" ? 130 : 170}
            tickFormatter={truncateTick}
            tick={{ fontSize: 11, fill: CHART_TOKENS.navy }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip cursor={{ fill: CHART_TOKENS.blueTint }} content={<ChartTooltip />} />
          <Bar dataKey="count" fill={CHART_TOKENS.blue} isAnimationActive={false} barSize={14} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Shared upright publication-year chart, including empty years within the evidence range. */
export function PublicationYearsChart({
  data,
  size = "full",
}: {
  data: Record<string, number>;
  size?: ChartSize;
}) {
  const rows = fillYearRange(data);
  if (rows.length === 0) return null;
  return (
    <div className={`${size === "compact" ? "h-44" : "h-64"} min-w-0`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke={CHART_TOKENS.grid} />
          <XAxis
            dataKey="label"
            interval="preserveStartEnd"
            minTickGap={18}
            tick={{ fontSize: 11, fill: CHART_TOKENS.navy }}
            axisLine={{ stroke: CHART_TOKENS.grid }}
            tickLine={false}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fontSize: 11, fill: CHART_TOKENS.text }}
            width={28}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip cursor={{ fill: CHART_TOKENS.blueTint }} content={<ChartTooltip />} />
          <Bar dataKey="count" fill={CHART_TOKENS.blue} isAnimationActive={false} maxBarSize={36} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
