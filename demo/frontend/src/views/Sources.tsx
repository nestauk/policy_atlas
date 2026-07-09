// Every source the analysis touched — what happened to it, and why.
// Nothing is silently dropped; screened-out rows stay, with reasons.

import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type EvidenceRow } from '../api'
import { screenHover, SourceLink, STATUS_LABEL, STATUS_TONE } from '../sourcePanel'
import { Dot, Tip } from '../ui'

const INCLUDED = new Set([
  'relevant', 'not_selected', 'selected', 'read_in_full', 'findings_extracted', 'cited', 'unavailable',
])

type Filter = 'all' | 'included' | 'screened_out' | 'cited'

export default function Sources() {
  const { id } = useParams<{ id: string }>()
  const [rows, setRows] = useState<EvidenceRow[]>([])
  const [filter, setFilter] = useState<Filter>('all')

  useEffect(() => {
    api.getEvidence(id!).then(setRows).catch(() => {})
  }, [id])

  const counts = useMemo(
    () => ({
      all: rows.length,
      included: rows.filter((r) => INCLUDED.has(r.status)).length,
      screened_out: rows.filter((r) => r.status === 'screened_out').length,
      cited: rows.filter((r) => r.cited).length,
    }),
    [rows],
  )

  const visible = rows.filter((r) =>
    filter === 'all' ? true
    : filter === 'included' ? INCLUDED.has(r.status)
    : filter === 'cited' ? r.cited
    : r.status === 'screened_out',
  )

  return (
    <main className="mx-auto max-w-[1180px] px-8 py-8">
      <h1 className="font-display text-[24px] font-extrabold text-navy">Sources</h1>
      <p className="mt-1 text-[13px] text-grey">
        Every source the analysis touched — what happened to it, and why.
      </p>

      <div className="mt-3 text-[13px]">
        <span className="font-semibold text-navy">{counts.included} included</span>
        <span className="text-grey"> · {counts.screened_out} screened out </span>
        <button className="font-semibold text-blue hover:underline" onClick={() => setFilter('screened_out')}>
          see exclusions
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {(
          [
            ['all', `All ${counts.all}`],
            ['included', `Included ${counts.included}`],
            ['screened_out', `Screened out ${counts.screened_out}`],
            ['cited', `Cited ${counts.cited}`],
          ] as [Filter, string][]
        ).map(([key, label]) => (
          <button key={key} className={`chip ${filter === key ? 'chip--blue' : ''}`} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>

      <div className="mt-5 bg-white shadow-card ring-1 ring-line">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b hairline">
              {['Source', 'Year', 'Origin', 'Status', 'Strength', 'Cited'].map((h) => (
                <th key={h} className="px-4 py-2.5 text-[11px] font-extrabold uppercase tracking-[.06em] text-grey">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((r) => (
              <tr key={r.source_id} className="border-b hairline align-top">
                <td className="max-w-[430px] px-4 py-3">
                  <SourceLink sourceId={r.source_id} title={r.title} className="!text-[13px] leading-snug">
                    {r.title}
                  </SourceLink>
                  {r.venue && <div className="mt-0.5 text-[11.5px] text-grey">{r.venue}</div>}
                </td>
                <td className="px-4 py-3 text-[12.5px] text-navy">{r.year ?? ''}</td>
                <td className="px-4 py-3"><span className="chip chip--soft">{r.origin}</span></td>
                <td className="px-4 py-3">
                  <Tip content={<div className="max-w-[240px] text-[12px] leading-snug text-navy">{screenHover(r) || STATUS_LABEL[r.status]}</div>}>
                    <span className="flex cursor-default items-center gap-2 text-[12.5px] font-medium text-navy">
                      <Dot tone={STATUS_TONE[r.status] ?? 'idle'} /> {STATUS_LABEL[r.status] ?? r.status}
                    </span>
                  </Tip>
                </td>
                <td className="px-4 py-3">
                  {r.appraisal_label && (
                    <span className="text-[11px] font-extrabold uppercase tracking-wide text-navy">{r.appraisal_label}</span>
                  )}
                </td>
                <td className="px-4 py-3 text-green-text">{r.cited ? '✓' : ''}</td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[13px] text-grey">
                  Sources appear here as soon as the search runs.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  )
}
