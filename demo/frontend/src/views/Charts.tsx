// Landscape charts: evidence types, publication years, publication countries,
// themes. Every distribution is over the screened-in set only (API invariant).

import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Landscape } from '../api'
import { HBar, PaneH } from '../ui'

const PALETTE = ['#0000FF', '#97D9E3', '#A59BEE', '#18A48C', '#FDB633', '#D2C9C0', '#F6A4B7']
const GREY = '#646363'
const tipStyle = { fontSize: 11, border: '1px solid #e4e4e7', borderRadius: 0 }

export default function Charts({ landscape }: { landscape: Landscape }) {
  const types = Object.entries(landscape.evidence_types).map(([name, value]) => ({ name, value }))
  const years = Object.entries(landscape.years)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([year, count]) => ({ year, count }))
  const countries = Object.entries(landscape.publication_countries ?? {}).sort(([, a], [, b]) => b - a)
  const cMax = countries[0]?.[1] ?? 1

  return (
    <div className="space-y-5">
      <h3 className="font-display text-[17px] font-semibold text-navy">The evidence landscape</h3>

      {types.length > 0 && (
        <div className="card anim-rise">
          <PaneH className="mb-2">Evidence types</PaneH>
          {/* fixed-size donut: ResponsiveContainer can measure 0 at mount and collapse */}
          <div className="flex justify-center">
            <PieChart width={210} height={210}>
              <Pie data={types} dataKey="value" nameKey="name" innerRadius={48} outerRadius={78} paddingAngle={2} stroke="none">
                {types.map((_, i) => (
                  <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tipStyle} formatter={(v: number, n: string) => [`${v} sources`, n]} />
            </PieChart>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
            {types.map((t, i) => (
              <span key={t.name} className="flex items-center gap-1.5 text-[11px] text-grey">
                <span className="h-2.5 w-2.5" style={{ background: PALETTE[i % PALETTE.length] }} />
                {t.name} ({t.value})
              </span>
            ))}
          </div>
        </div>
      )}

      {years.length > 0 && (
        <div className="card anim-rise">
          <PaneH className="mb-2">Publication years</PaneH>
          <ResponsiveContainer width="100%" height={190}>
            <BarChart data={years} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}>
              <XAxis dataKey="year" tick={{ fontSize: 11, fill: GREY }} tickLine={false} axisLine={{ stroke: '#e4e4e7' }} />
              <YAxis tick={{ fontSize: 11, fill: GREY }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tipStyle} formatter={(v: number) => [`${v} sources`, 'Published']} />
              <Bar dataKey="count" fill="#0000FF" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {countries.length > 0 && (
        <div className="card anim-rise">
          <PaneH className="mb-1">Where sources were published</PaneH>
          <p className="mb-3 text-[11px] text-grey">
            Publication country — where sources were published, not where the studies were conducted.
          </p>
          <div className="space-y-1.5">
            {countries.map(([label, value]) => (
              <div key={label} className="flex items-center gap-3">
                <div className="w-40 shrink-0 truncate text-right text-[12px] font-medium text-navy">{label}</div>
                <HBar value={value} max={cMax} />
                <span className="w-6 shrink-0 text-[12px] font-bold text-navy">{value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {landscape.themes.length > 0 && (
        <div className="card anim-rise">
          <PaneH className="mb-2">Themes</PaneH>
          <div className="space-y-2.5">
            {[...landscape.themes]
              .sort((a, b) => b.size - a.size)
              .map((t) => (
                <div key={t.name} className="flex items-baseline gap-3">
                  <span className="font-display text-[16px] font-bold text-blue">{t.size}</span>
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold text-navy">{t.name}</div>
                    <div className="text-[12px] text-grey">{t.description}</div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
