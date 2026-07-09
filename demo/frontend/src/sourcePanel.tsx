// The source dossier slide-over — everything the backend knows about one
// source — plus SourceLink, the one way any view opens it.

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react'
import { api } from './api'
import type { EvidenceRow, Finding, SourceDossier } from './api'
import { Dot, KV, PaneH, SlideOver } from './ui'

const norm = (t: string) => t.toLowerCase().replace(/[^a-z0-9 ]/g, '').trim()

interface PanelCtx {
  open(target: { sourceId?: string; title?: string }): void
  resolves(target: { sourceId?: string; title?: string }): boolean
}

const Ctx = createContext<PanelCtx | null>(null)

export function useSourcePanel(): PanelCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useSourcePanel outside provider')
  return ctx
}

export const STATUS_LABEL: Record<string, string> = {
  found: 'Found', screened_out: 'Screened out', relevant: 'Included',
  not_selected: 'Included — not shortlisted', selected: 'Shortlisted',
  read_in_full: 'Read in full', findings_extracted: 'Findings extracted',
  cited: 'Cited in the evidence base', unavailable: 'Included — abstract only',
}

export const STATUS_TONE: Record<string, 'progress' | 'done' | 'paused' | 'idle'> = {
  found: 'idle', screened_out: 'idle', relevant: 'progress', not_selected: 'progress',
  selected: 'progress', read_in_full: 'progress', findings_extracted: 'done',
  cited: 'done', unavailable: 'paused',
}

export function screenHover(row: EvidenceRow): string {
  const bits: string[] = []
  if (row.screen_confidence != null) bits.push(`Screening confidence: ${Math.round(row.screen_confidence * 100)}%`)
  if (row.screen_basis) bits.push(row.screen_basis === 'title_only' ? 'Read: title only' : 'Read: title + abstract')
  if (row.screen_stage === 2) bits.push('Confirmed against full text')
  if (row.status_reason) bits.push(row.status_reason)
  return bits.join(' · ')
}

export function SourcePanelProvider({ projectId, children }: { projectId: string; children: ReactNode }) {
  const [target, setTarget] = useState<{ sourceId?: string; title?: string } | null>(null)
  const [rows, setRows] = useState<EvidenceRow[]>([])
  const [findings, setFindings] = useState<Finding[]>([])

  useEffect(() => {
    api.getEvidence(projectId).then(setRows).catch(() => {})
    api.getFindings(projectId).then(setFindings).catch(() => {})
  }, [projectId, target != null])

  const resolveRow = useCallback(
    (t: { sourceId?: string; title?: string }): EvidenceRow | null => {
      if (t.sourceId) {
        const byId = rows.find((r) => r.source_id === t.sourceId)
        if (byId) return byId
      }
      if (t.title) {
        return (
          rows.find((r) => r.title === t.title) ??
          rows.find((r) => norm(r.title) === norm(t.title!)) ??
          null
        )
      }
      return null
    },
    [rows],
  )

  const ctx = useMemo<PanelCtx>(
    () => ({
      open: (t) => setTarget(t),
      resolves: (t) => resolveRow(t) != null,
    }),
    [resolveRow],
  )

  const row = target ? resolveRow(target) : null

  return (
    <Ctx.Provider value={ctx}>
      {children}
      <SlideOver open={!!row} onClose={() => setTarget(null)} title="Source" z={50}>
        {row && (
          <Dossier projectId={projectId} row={row} findings={findings.filter((f) => f.source_id === row.source_id)} />
        )}
      </SlideOver>
    </Ctx.Provider>
  )
}

function Dossier({ projectId, row, findings }: { projectId: string; row: EvidenceRow; findings: Finding[] }) {
  const [dossier, setDossier] = useState<SourceDossier | null>(null)
  useEffect(() => {
    setDossier(null)
    api.getSource(projectId, row.source_id).then(setDossier).catch(() => {})
  }, [projectId, row.source_id])

  const d = dossier
  const byAsserter = new Map<string, { tag: string; tag_type: string }[]>()
  for (const t of d?.tags ?? []) {
    byAsserter.set(t.asserted_by, [...(byAsserter.get(t.asserted_by) ?? []), t])
  }

  return (
    <div className="space-y-6">
      <header>
        <h3 className="text-[16px] font-bold leading-snug text-navy">{row.title}</h3>
        <div className="mt-1 text-[12.5px] text-grey">
          {[row.year, row.venue].filter(Boolean).join(' · ')}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="chip chip--soft">{row.origin}</span>
          {row.url && (
            <a className="chip chip--blue" href={row.url} target="_blank" rel="noreferrer">
              Open original ↗
            </a>
          )}
        </div>
      </header>

      {d?.abstract && (
        <section>
          <PaneH className="mb-1.5">About</PaneH>
          <p className="text-[13px] italic leading-relaxed text-grey">{d.abstract}</p>
        </section>
      )}

      <section>
        <PaneH className="mb-1.5">What happened to it</PaneH>
        <div className="flex items-center gap-2 text-[13px] font-medium text-navy">
          <Dot tone={STATUS_TONE[row.status] ?? 'idle'} /> {STATUS_LABEL[row.status] ?? row.status}
        </div>
        <p className="mt-1 text-[12.5px] text-grey">{screenHover(row)}</p>
      </section>

      {(row.evidence_type || row.appraisal_label) && (
        <section>
          <PaneH className="mb-1.5">Quality</PaneH>
          <KV
            rows={[
              ...(row.evidence_type ? ([['Evidence type', row.evidence_type]] as [string, ReactNode][]) : []),
              ...(row.appraisal_label ? ([['Appraised strength', row.appraisal_label]] as [string, ReactNode][]) : []),
            ]}
          />
        </section>
      )}

      {d && (d.doi || d.publisher_org || d.cited_by_count != null) && (
        <section>
          <PaneH className="mb-1.5">Details</PaneH>
          <KV
            rows={
              [
                d.publisher_org && ['Publisher', d.publisher_org],
                d.record_type && ['Record type', d.record_type],
                d.language && ['Language', d.language],
                d.cited_by_count != null && ['Cited by', d.cited_by_count],
                d.fwci != null && ['Field-weighted impact', d.fwci],
              ].filter(Boolean) as [string, ReactNode][]
            }
          />
        </section>
      )}

      {byAsserter.size > 0 && (
        <section>
          <PaneH className="mb-1.5">Tags</PaneH>
          <p className="mb-2 text-[11px] text-grey">
            Tags carry their asserter — the same tag from two sources is two assertions, never merged.
          </p>
          {[...byAsserter.entries()].map(([asserter, tags]) => (
            <div key={asserter} className="mb-2">
              <div className="mb-1 text-[10.5px] font-bold uppercase tracking-wide text-navy-40">
                Tagged by {asserter}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {tags.map((t, i) => (
                  <span key={i} className={`chip ${t.tag_type === 'methodological_structural' ? 'chip--blue' : 'chip--soft'} !whitespace-normal`}>
                    {t.tag}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      {d && d.cited_claims.length > 0 && (
        <section>
          <PaneH className="mb-1.5">Cited in the evidence base</PaneH>
          <div className="space-y-3">
            {d.cited_claims.map((c, i) => (
              <div key={i} className="border-l-2 border-blue-edge pl-3">
                <p className="text-[13px] leading-snug text-navy">{c.claim}</p>
                <p className="mt-1 text-[12px] italic text-grey">
                  “{c.quote}” {c.verified && <span className="text-green-text">✓</span>}
                </p>
                {c.section && (
                  <div className="mt-0.5 text-[10.5px] font-bold uppercase tracking-wide text-navy-40">{c.section}</div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <section>
        <PaneH className="mb-1.5">Findings from this source</PaneH>
        {findings.length === 0 ? (
          <p className="text-[12.5px] text-grey">No findings extracted from this source.</p>
        ) : (
          <div className="space-y-2.5">
            {findings.map((f) => (
              <div key={f.finding_id} className="text-[13px] leading-snug">
                <span className="font-medium text-navy">{f.intervention}</span>
                <span className="text-grey"> → {f.outcome}</span>
                <DirectionChip direction={f.direction} className="ml-1.5 align-middle" />
                {f.quote && <p className="mt-0.5 text-[12px] italic text-grey">“{f.quote}”</p>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export function DirectionChip({ direction, className = '' }: { direction: Finding['direction']; className?: string }) {
  const map: Record<Finding['direction'], [string, string]> = {
    positive: ['chip--green', 'Positive'],
    negative: ['chip--orange', 'Negative'],
    no_effect: ['chip--soft', 'No effect'],
    mixed: ['chip--yellow', 'Mixed'],
    unclear: ['chip--soft italic', 'Unclear'],
  }
  const [tone, label] = map[direction]
  return <span className={`chip ${tone} ${className}`}>{label}</span>
}

export function SourceLink({ sourceId, title, children, className = '' }: {
  sourceId?: string
  title?: string
  children: ReactNode
  className?: string
}) {
  const panel = useSourcePanel()
  const target = { sourceId, title }
  if (!panel.resolves(target)) return <span className={className}>{children}</span>
  return (
    <span
      role="button"
      tabIndex={0}
      className={`cursor-pointer font-semibold text-navy transition-colors hover:text-blue hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue ${className}`}
      onClick={() => panel.open(target)}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), panel.open(target))}
    >
      {children}
    </span>
  )
}
