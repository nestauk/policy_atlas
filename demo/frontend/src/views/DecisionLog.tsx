// The audit trail, readable: every stage, count and check-in from the
// canonical event log — expandable to the numbers behind each entry.

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type DecisionEntry } from '../api'

export default function DecisionLog() {
  const { id } = useParams<{ id: string }>()
  const [entries, setEntries] = useState<DecisionEntry[]>([])
  const [open, setOpen] = useState<number | null>(null)

  useEffect(() => {
    api.getDecisions(id!).then(setEntries).catch(() => {})
  }, [id])

  return (
    <main className="mx-auto max-w-[860px] px-8 py-8">
      <h1 className="font-display text-[24px] font-extrabold text-navy">Decision log</h1>
      <p className="mt-1 text-[13px] text-grey">
        The audit trail — every stage, count and check-in, straight from the project's event log.
      </p>

      <div className="mt-6 space-y-0 bg-white shadow-card ring-1 ring-line">
        {entries.map((e, i) => {
          const expandable = Object.keys(e.detail ?? {}).length > 0
          const expanded = open === i
          const time = new Date(e.at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
          return (
            <div key={i} className={`border-b hairline last:border-b-0 ${e.kind === 'checkin' ? 'border-l-2 !border-l-yellow-edge bg-yellow-tint/40' : ''}`}>
              <button
                className={`flex w-full items-baseline gap-4 px-5 py-3 text-left ${expandable ? 'cursor-pointer hover:bg-blue-tint2' : 'cursor-default'}`}
                onClick={() => expandable && setOpen(expanded ? null : i)}
                aria-expanded={expandable ? expanded : undefined}
              >
                <span className="w-11 shrink-0 text-[11px] tabular-nums text-grey">{time}</span>
                <span className="flex-1 text-[13px] leading-snug text-navy">{e.text}</span>
                {expandable && <span className="text-[11px] text-grey">{expanded ? '▾' : '▸'}</span>}
              </button>
              {expanded && (
                <dl className="grid grid-cols-1 gap-x-8 gap-y-1 bg-sand-20 px-5 py-3 pl-20 sm:grid-cols-2">
                  {Object.entries(e.detail).map(([k, v]) => (
                    <div key={k} className="flex items-baseline justify-between gap-3 text-[12.5px]">
                      <dt className="text-grey">{k}</dt>
                      <dd className="text-right font-medium text-navy">{String(v)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          )
        })}
        {entries.length === 0 && (
          <p className="px-5 py-8 text-center text-[13px] text-grey">
            The log fills in as the analysis runs.
          </p>
        )}
      </div>
    </main>
  )
}
