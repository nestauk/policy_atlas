// The findings layer: every extracted intervention→outcome result, expandable
// to the full reported numbers, filterable by the grouping run's facet groups.

import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type Finding, type Groups } from '../api'
import { DirectionChip, SourceLink } from '../sourcePanel'
import { PaneH, Tip } from '../ui'

const STAT_LABELS: [string, string][] = [
  ['effect_size', 'Effect size'], ['ci', '95% CI'], ['se', 'SE'], ['p_value', 'p'],
  ['n', 'N'], ['k', 'Studies (k)'], ['i2', 'I²'], ['tau2', 'τ²'],
]

const normFacet = (f: string) => f.toLowerCase().replace(/ type$/, '').trim()

export default function Findings() {
  const { id } = useParams<{ id: string }>()
  const [findings, setFindings] = useState<Finding[]>([])
  const [groups, setGroups] = useState<Groups | null>(null)
  const [filter, setFilter] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    api.getFindings(id!).then(setFindings).catch(() => {})
    api.getGroups(id!).then(setGroups).catch(() => {})
  }, [id])

  const interventionFacet = useMemo(
    () => groups?.facets.find((f) => normFacet(f.facet) === 'intervention') ?? null,
    [groups],
  )
  const groupOf = (f: Finding): string | null => {
    for (const [facet, label] of Object.entries(f.groups)) {
      if (normFacet(facet) === 'intervention') return label
    }
    return null
  }
  const rows = filter ? findings.filter((f) => groupOf(f) === filter) : findings

  return (
    <main className="mx-auto max-w-[1180px] px-8 py-8">
      <h1 className="font-display text-[24px] font-extrabold text-navy">Findings</h1>
      <p className="mt-1 text-[13px] text-grey">
        Every finding pulled from the sources — intervention, outcome, direction, and the exact words it rests on.
      </p>

      {interventionFacet && interventionFacet.groups.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          <button className={`chip ${filter === null ? 'chip--blue' : ''}`} onClick={() => setFilter(null)}>
            All {findings.length}
          </button>
          {[...interventionFacet.groups]
            .sort((a, b) => b.size - a.size)
            .slice(0, 8)
            .map((g) => (
              <button
                key={g.label}
                className={`chip ${filter === g.label ? 'chip--blue' : ''}`}
                onClick={() => setFilter(filter === g.label ? null : g.label)}
              >
                {g.label}
              </button>
            ))}
        </div>
      )}

      <div className="mt-5 bg-white shadow-card ring-1 ring-line">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b hairline">
              {['', 'Intervention', 'Outcome', 'Direction', 'Grouped as', 'Source'].map((h) => (
                <th key={h} className="px-4 py-2.5 text-[11px] font-extrabold uppercase tracking-[.06em] text-grey">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => {
              const expanded = open === f.finding_id
              const group = groupOf(f)
              return (
                <FindingRow
                  key={f.finding_id}
                  f={f}
                  group={group}
                  expanded={expanded}
                  onToggle={() => setOpen(expanded ? null : f.finding_id)}
                />
              )
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[13px] text-grey">
                  No findings yet — they appear once the close-reading stage has run.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  )
}

function FindingRow({ f, group, expanded, onToggle }: {
  f: Finding
  group: string | null
  expanded: boolean
  onToggle: () => void
}) {
  const stats = STAT_LABELS.filter(([k]) => f.statistics[k] != null)
  return (
    <>
      <tr
        className="cursor-pointer border-b hairline align-top transition-colors hover:bg-blue-tint2"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <td className="w-8 px-4 py-3 text-[11px] text-grey">{expanded ? '▾' : '▸'}</td>
        <td className="max-w-[280px] px-4 py-3 text-[13px] font-medium leading-snug text-navy">{f.intervention}</td>
        <td className="max-w-[220px] px-4 py-3 text-[13px] leading-snug text-navy">{f.outcome}</td>
        <td className="px-4 py-3">
          <Tip content={<div className="text-[12px] text-navy">{[f.population, f.study_design].filter(Boolean).join(' · ') || 'No detail reported'}</div>}>
            <span><DirectionChip direction={f.direction} /></span>
          </Tip>
        </td>
        <td className="px-4 py-3">{group && <span className="chip chip--soft !whitespace-normal">{group}</span>}</td>
        <td className="max-w-[220px] px-4 py-3 text-[12px] leading-snug text-grey" onClick={(e) => e.stopPropagation()}>
          <SourceLink sourceId={f.source_id} title={f.source_title} className="!text-[12px] !font-normal">
            {f.source_title}
          </SourceLink>
        </td>
      </tr>
      {expanded && (
        <tr className="border-b hairline bg-sand-20">
          <td />
          <td colSpan={5} className="px-4 py-4">
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <PaneH className="mb-2">Reported numbers</PaneH>
                {stats.length === 0 && !f.estimate_level ? (
                  <p className="text-[12.5px] text-grey">No numbers reported — recorded as direction only.</p>
                ) : (
                  <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-1 text-[12.5px]">
                    {stats.map(([k, label]) => (
                      <div key={k} className="contents">
                        <dt className="text-grey">{label}</dt>
                        <dd className="font-medium text-navy">{String(f.statistics[k])}</dd>
                      </div>
                    ))}
                    {f.estimate_level && (
                      <div className="contents"><dt className="text-grey">Estimate level</dt><dd className="font-medium text-navy">{f.estimate_level}</dd></div>
                    )}
                    {f.causality && (
                      <div className="contents"><dt className="text-grey">Causality by design</dt><dd className="font-medium text-navy">{f.causality.split('_').join(' ')}</dd></div>
                    )}
                    {f.comparator && (
                      <div className="contents"><dt className="text-grey">Comparator</dt><dd className="font-medium text-navy">{f.comparator}</dd></div>
                    )}
                  </dl>
                )}
                {f.is_primary && <span className="chip chip--blue mt-2">Primary outcome</span>}
                {f.stratum_qualifiers.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {f.stratum_qualifiers.map((q, i) => (
                      <span key={i} className="chip chip--soft">{q.type}: {q.value}</span>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <PaneH className="mb-2">The exact words</PaneH>
                {f.quote ? (
                  <p className="text-[12.5px] italic leading-relaxed text-grey">
                    “{f.quote}” {f.quote_verified && <span className="not-italic text-green-text">✓ verified</span>}
                  </p>
                ) : (
                  <p className="text-[12.5px] text-grey">No anchoring quote recorded.</p>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
