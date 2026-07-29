import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from "recharts";

import { scrub } from "../../lib/scrub";

const CHART_TOKENS = {
  grid: "var(--color-line)",
  text: "var(--color-grey)",
  navy: "var(--color-navy)",
  blue: "var(--color-blue)",
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

function chartHeight(size: ChartSize): string {
  return size === "compact" ? "h-44" : "h-64";
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

/** Shared horizontal distribution chart for evidence types and publication geography. */
export function EvidenceDistributionChart({
  data,
  size = "full",
}: {
  data: Record<string, number>;
  size?: ChartSize;
}) {
  const rows = Object.entries(data)
    .map(([label, count]) => ({ label: scrub(label), count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 12);
  if (rows.length === 0) return null;
  return (
    <div className={`${chartHeight(size)} min-w-0`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 24 }}>
          <CartesianGrid horizontal={false} stroke={CHART_TOKENS.grid} />
          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11, fill: CHART_TOKENS.text }} />
          <YAxis type="category" dataKey="label" width={150} tick={{ fontSize: 11, fill: CHART_TOKENS.navy }} />
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
    <div className={`${chartHeight(size)} min-w-0`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke={CHART_TOKENS.grid} />
          <XAxis
            dataKey="label"
            interval="preserveStartEnd"
            minTickGap={18}
            tick={{ fontSize: 11, fill: CHART_TOKENS.navy }}
          />
          <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: CHART_TOKENS.text }} width={28} />
          <Bar dataKey="count" fill={CHART_TOKENS.blue} isAnimationActive={false} maxBarSize={36} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
