// The evidence artifact's Activity log: the plan, "Where I looked", "How it got
// there", the funnel, the landscape, findings and the decision log — every
// record of how the evidence base was made, in one place.

import { useState, type ReactNode } from 'react'
import type { ScopeConstraints } from '../../api'
import { useProject, type StageInfo } from '../../store'
import { CountUp, formatElapsed, HBar, PaneH, Spinner, Tip } from '../../ui'
import Charts from '../Charts'
import { FindingsSection } from '../Findings'
import { DecisionLogList } from '../DecisionLog'

const SOURCES_LABEL: Record<string, string> = {
  academic_only: 'Academic research (OpenAlex)',
  grey_lit_only: 'Policy literature (Overton)',
  both: 'Academic + policy (OpenAlex, Overton)',
}
const SEARCH_EFFORT_LABEL: Record<string, string> = {
  rapid: 'Rapid — top sources, fast pass',
  standard: 'Standard — a balanced sweep',
  deep: 'Deep — systematic-style sweep',
}
const ANALYSIS_DEPTH_LABEL: Record<string, string> = {
  landscape: 'Landscape — mapping the terrain',
  standard: 'Standard — full write-up, every claim cited',
  deep: 'Deep — the closest reading',
}
const STEERING_MODE_LABEL: Record<string, string> = {
  frequent: 'At every step',
  moderate: 'When something needs your judgement',
  minimal: "Only if it can't proceed",
  unattended: 'Unattended (no pauses)',
}

const label = (map: Record<string, string>, key?: string | null): string => (key ? map[key] ?? key : '')
const yearOf = (iso: string): string => (/^(\d{4})/.exec(iso)?.[1] ?? iso)
const backendLabel = (b: string) =>
  b === 'openalex' ? 'OpenAlex · academic research' : b === 'overton' ? 'Overton · policy documents' : b

function scopeChips(sc?: ScopeConstraints | null): string[] {
  if (!sc) return []
  const chips: string[] = []
  if (sc.published_after) chips.push(`Published after ${yearOf(sc.published_after)}`)
  if (sc.published_before) chips.push(`Published before ${yearOf(sc.published_before)}`)
  const geo = sc.country_group
    ? sc.country_group.label + (sc.country_group.countries?.length ? ` (${sc.country_group.countries.join(', ')})` : '')
    : [...new Set([sc.publisher_country, ...(sc.author_affiliation_countries ?? [])])].filter(Boolean).join(', ')
  if (geo) chips.push(`Geography: ${geo}`)
  return chips
}

export default function EvidenceActivity() {
  const { state } = useProject()
  const hasLandscape = !!state.landscape && Object.keys(state.landscape.evidence_types).length > 0
  const hasGroups = !!state.groups && state.groups.facets.length > 0
  const searching = ['acquire', 'screen_abstract', 'screen_full'].some(
    (s) => state.stages[s]?.status === 'active',
  )

  return (
    <div className="thin-scroll h-full overflow-y-auto px-7 py-6" style={{ scrollbarGutter: 'stable' }}>
      {state.phase === 'analysing' && <ProgressStrip />}

      <div className="space-y-5">
        <PlanBlock />
        {searching && <SearchCard />}
        {state.coverage && <CoverageCard />}
        {state.phase === 'analysing' && <ActivityCard />}

        <div className="card">
          <PaneH className="mb-3">How it got there</PaneH>
          <Timeline />
        </div>

        {state.funnel?.found != null && (
          <div className="card">
            <PaneH className="mb-3">From sources to evidence</PaneH>
            <Funnel />
          </div>
        )}

        {hasLandscape && <Charts landscape={state.landscape!} />}

        {hasGroups && (
          <div className="card">
            <PaneH className="mb-3">Findings</PaneH>
            <FindingsSection />
          </div>
        )}

        <div className="card">
          <PaneH className="mb-3">Decision log</PaneH>
          <DecisionLogList />
        </div>
      </div>
    </div>
  )
}

/* ---------------- plan ---------------- */

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <PaneH>{label}</PaneH>
      <div className="mt-2">{children}</div>
    </div>
  )
}

function PlanBlock() {
  const { state, startAnalysis } = useProject()
  const [starting, setStarting] = useState(false)
  const plan = state.plan
  if (!plan || (!plan.question && plan.steps.length === 0)) {
    return (
      <div className="card">
        <PaneH>Plan</PaneH>
        <p className="mt-2 max-w-md text-sm text-grey">
          Forms here as you talk in the chat. Nothing runs until you approve it.
        </p>
      </div>
    )
  }

  const scopingNotes = plan.scoping_notes ?? []
  const screeningCriteria = plan.screening_criteria ?? []
  const constraints = scopeChips(plan.scope_constraints)
  const steps = plan.steps ?? []
  const canStart = plan.ready && state.phase === 'planning'
  const settings: [string, string][] = (
    [
      ['Search effort', label(SEARCH_EFFORT_LABEL, plan.search_effort)],
      ['Analysis depth', label(ANALYSIS_DEPTH_LABEL, plan.analysis_depth)],
      ['Sources', plan.backend_scope ? SOURCES_LABEL[plan.backend_scope] ?? plan.backend_scope : ''],
      ['Check-ins', label(STEERING_MODE_LABEL, plan.steering_mode)],
    ] as [string, string][]
  ).filter(([, v]) => v)

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between">
        <PaneH>The plan</PaneH>
        <div className="flex items-center gap-2">
          {plan.time_band && <span className="text-[12px] text-grey">{plan.time_band}</span>}
          <span className={`chip ${plan.ready ? 'chip--green' : 'chip--soft'}`}>{plan.ready ? 'ready' : 'forming…'}</span>
        </div>
      </div>

      <Field label="Question">
        <p className="text-[15px] font-semibold leading-snug text-navy">
          {plan.question ?? <span className="text-navy-40">Not set yet</span>}
        </p>
      </Field>

      {scopingNotes.length > 0 && (
        <Field label="Focus">
          <div className="flex flex-wrap gap-2">
            {scopingNotes.map((f) => <span key={f} className="chip chip--soft">{f}</span>)}
          </div>
          {screeningCriteria.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[12px] text-grey">
              {screeningCriteria.map((c) => <li key={c}>{c}</li>)}
            </ul>
          )}
        </Field>
      )}

      {constraints.length > 0 && (
        <Field label="Constraints">
          <div className="flex flex-wrap gap-2">
            {constraints.map((c) => <span key={c} className="chip chip--soft">{c}</span>)}
          </div>
        </Field>
      )}

      {settings.length > 0 && (
        <div
          className="grid gap-px border hairline bg-line"
          style={{ gridTemplateColumns: `repeat(${Math.min(settings.length, 4)}, minmax(0, 1fr))` }}
        >
          {settings.map(([k, v]) => (
            <div key={k} className="bg-white px-3.5 py-2.5">
              <div className="text-[10.5px] font-extrabold uppercase tracking-[.06em] text-navy-40">{k}</div>
              <div className="mt-0.5 text-[13px] font-medium leading-snug text-navy">{v}</div>
            </div>
          ))}
        </div>
      )}

      {steps.length > 0 && (
        <Field label="Steps">
          <ol className="space-y-2.5">
            {steps.map((s) => (
              <li key={s.stage} className="flex items-start gap-2.5 text-[13px] text-navy">
                <span className="mt-0.5 h-3 w-3 shrink-0 border hairline" />
                <div>
                  <div>{s.label}</div>
                  {s.blurb && <div className="text-[12px] text-grey">{s.blurb}</div>}
                </div>
              </li>
            ))}
          </ol>
        </Field>
      )}

      {canStart && (
        <div className="border-t hairline pt-4">
          <button
            className="btn w-full justify-center !py-3.5 !text-[14px]"
            disabled={starting}
            onClick={() => { setStarting(true); void startAnalysis() }}
          >
            {starting ? 'Starting…' : 'Start the analysis'}
          </button>
          <p className="mt-2 text-center text-[12px] text-grey">
            {plan.time_band ? `${plan.time_band} · ` : ''}You can steer or pause at any check-in.
          </p>
        </div>
      )}
    </div>
  )
}

/* ---------------- journey pieces ---------------- */

function ProgressStrip() {
  const { state } = useProject()
  if (state.stageOrder.length === 0) return null
  return (
    <div className="mb-1">
      <div className="flex gap-1">
        {state.stageOrder.map((s) => {
          const st = state.stages[s]?.status
          return (
            <div
              key={s}
              className={`h-1 flex-1 ${st === 'done' ? 'bg-blue' : st === 'failed' ? 'bg-orange' : 'anim-breathe bg-blue'}`}
            />
          )
        })}
      </div>
      {state.paused && (
        <div className="mt-1 text-right text-[12px] font-semibold text-yellow-text">Paused — waiting on your answer</div>
      )}
    </div>
  )
}

function CoverageCard() {
  const { state } = useProject()
  const coverage = state.coverage!
  return (
    <div className="card">
      <PaneH className="mb-2">Where I looked</PaneH>
      {(coverage.backends_detail?.length ?? 0) > 0 && (
        <div className="mb-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {coverage.backends_detail!.map((b) => (
            <div key={b.backend} className="border hairline p-3.5">
              <div className="flex items-baseline justify-between">
                <span className="text-[13px] font-bold text-navy">{backendLabel(b.backend)}</span>
                <span className="text-[12px] text-grey">
                  <span className="font-display text-[18px] font-bold text-blue">{b.results}</span>
                  {' results · '}
                  <span className="font-display text-[18px] font-bold text-blue">{b.relevant}</span>
                  {' relevant'}
                </span>
              </div>
              <div className="thin-scroll mt-2 max-h-28 space-y-0.5 overflow-y-auto">
                {b.queries.map((q, i) => (
                  <div key={i} className="flex items-baseline justify-between gap-2 text-[11.5px]">
                    <span className="truncate italic text-grey">“{q.query}”</span>
                    <span className="shrink-0 text-navy-40">{q.results ?? '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {!coverage.backends_detail?.length && (
        <div className="text-sm font-medium text-navy">{coverage.backends.map(backendLabel).join(' · ')}</div>
      )}
      <p className="mt-1 text-[13px] text-navy">
        {coverage.summary ??
          (coverage.adequacy === 'adequate' ? 'Coverage judged adequate.' : 'Coverage judged thin — recorded, not hidden.')}
      </p>
    </div>
  )
}

function Timeline() {
  const { state } = useProject()
  const order = [...state.stageOrder]
  const seen = new Set(order)
  for (const s of state.plan?.steps ?? []) {
    if (!seen.has(s.stage)) { seen.add(s.stage); order.push(s.stage) }
  }
  const planned = new Map((state.plan?.steps ?? []).map((s) => [s.stage, s.label]))

  return (
    <ol className="space-y-2.5">
      {order.map((stage) => {
        const info: StageInfo | undefined = state.stages[stage]
        const lab = info?.label ?? planned.get(stage) ?? stage
        const status = info?.status
        const secs = typeof info?.summary?.seconds === 'number' ? info.summary.seconds : null
        const summary = info?.summary
          ? Object.entries(info.summary)
              .filter(([k, v]) => k !== 'seconds' && typeof v === 'number')
              .slice(0, 3)
              .map(([k, v]) => `${v} ${k.split('_').join(' ')}`)
              .join(' · ')
          : ''
        return (
          <li key={stage} className="flex items-start gap-2.5 text-[13px]">
            <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center">
              {status === 'done' ? (
                <span className="grid h-4 w-4 place-items-center bg-green text-[10px] font-bold text-white">✓</span>
              ) : status === 'failed' ? (
                <span className="grid h-4 w-4 place-items-center bg-orange text-[10px] font-bold text-white">!</span>
              ) : status === 'active' ? (
                <Spinner />
              ) : (
                <span className="h-3 w-3 border hairline" />
              )}
            </span>
            <div className="min-w-0">
              <Tip
                content={
                  <div className="text-[12px] leading-snug text-navy">
                    {info?.blurb || lab}
                    {status === 'done' && secs != null && <div className="mt-1 text-grey">Took {formatElapsed(secs)}</div>}
                    {status === 'failed' && info?.reason && <div className="mt-1 text-orange-text">{info.reason}</div>}
                  </div>
                }
              >
                <span className={`font-medium ${status ? 'text-navy' : 'text-navy-40'}`}>{lab}</span>
              </Tip>
              {status === 'done' && summary && <span className="ml-1.5 text-grey">— {summary}</span>}
              {status === 'done' && secs != null && <span className="ml-1.5 text-grey">· {formatElapsed(secs)}</span>}
              {status === 'failed' && (
                <span className="ml-1.5 text-orange-text">
                  {info?.skipped ? 'skipped — a prior step failed' : 'stopped — recorded, carrying on'}
                </span>
              )}
              {status === 'active' && info?.blurb && <div className="text-[12px] text-grey">{info.blurb}</div>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

const FUNNEL_DEFS: [keyof NonNullable<ReturnType<typeof useProject>['state']['funnel']>, string, string][] = [
  ['found', 'Sources found', 'Every record returned by the searches.'],
  ['relevant', 'Relevant', 'Kept after screening titles and abstracts against your question.'],
  ['quality_checked', 'Quality-checked', 'Labelled by evidence type and appraised for strength.'],
  ['read_in_full', 'Read in full', 'Full documents fetched and read.'],
  ['selected', 'Shortlisted', 'The strongest, most varied set chosen for close reading.'],
  ['findings', 'Findings extracted', 'Individual results pulled out with their exact quotes.'],
  ['cited', 'Cited in the evidence base', 'Sources the write-up rests on.'],
]

function Funnel() {
  const { state } = useProject()
  const f = state.funnel!
  const max = f.found ?? 1
  return (
    <div className="space-y-1.5">
      {FUNNEL_DEFS.map(([key, lab, def]) => {
        const v = f[key]
        if (v == null) return null
        return (
          <Tip key={String(key)} content={<div className="text-[12px] text-navy">{def}</div>} className="block">
            <div className="flex cursor-default items-center gap-3">
              <div className="w-44 shrink-0 text-right text-[12px] font-medium text-navy">{lab}</div>
              <HBar value={v} max={max} />
              <CountUp value={v} className="w-8 shrink-0 text-[12.5px] font-bold text-navy" />
            </div>
          </Tip>
        )
      })}
      {f.screened_out != null && (
        <p className="pl-[188px] text-[11.5px] text-grey">
          {f.screened_out} screened out — kept in the sources table with reasons.
        </p>
      )}
    </div>
  )
}

function SearchCard() {
  const { state } = useProject()
  const backends: [string, string][] = [
    ['openalex', 'OpenAlex · academic research'],
    ['overton', 'Overton · policy documents'],
  ]
  return (
    <div className="card">
      <PaneH className="mb-3">Searching</PaneH>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {backends.map(([key, lab]) => {
          const b = state.search[key]
          return (
            <div key={key} className="border hairline p-3.5">
              <div className="flex items-baseline justify-between">
                <span className="text-[13px] font-bold text-navy">{lab}</span>
                <CountUp value={b?.results ?? 0} className="font-display text-[22px] font-bold text-blue" />
              </div>
              <div className="mt-1 h-9 overflow-hidden">
                {(b?.queries ?? []).slice(-2).map((q, i) => (
                  <div key={i} className="anim-rise truncate text-[11.5px] italic text-grey">“{q}”</div>
                ))}
                {!b?.queries?.length && <div className="anim-breathe text-[11.5px] italic text-navy-40">preparing queries…</div>}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ActivityCard() {
  const { state } = useProject()
  const lines = state.activity.slice(-8)
  if (lines.length === 0) return null
  return (
    <div className="card">
      <PaneH className="mb-2">Activity</PaneH>
      <div className="space-y-1">
        {lines.map((l, i) => (
          <div
            key={l.id}
            className={`truncate border-l-2 pl-2 text-[12.5px] ${i === lines.length - 1 ? 'border-blue text-navy' : 'border-transparent text-grey'}`}
          >
            {l.text}
            {l.count > 1 && <span className="ml-1 font-semibold text-navy">× {l.count}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
