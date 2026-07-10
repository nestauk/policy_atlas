// The workspace: orchestrator thread on the left, the plan (planning) or the
// live journey (analysing/complete) on the right. Focus follows the
// information — once the analysis starts the chat narrows and the right pane
// takes the stage.

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { CheckinParams } from '../api'
import { useProject, type StageInfo, type ThreadMsg } from '../store'
import { CountUp, Dot, formatElapsed, HBar, PaneH, Spinner, Tip } from '../ui'
import Charts from './Charts'

export default function Workspace() {
  const { state } = useProject()
  const planning = state.phase === 'planning'
  return (
    <div
      className="grid h-[calc(100vh-58px)] transition-[grid-template-columns] duration-300 ease-in-out"
      style={{ gridTemplateColumns: planning ? '55fr 45fr' : '35fr 65fr' }}
    >
      <section className="flex min-w-0 flex-col border-r hairline bg-white">
        <Thread />
        <SuggestionChips />
        <Composer />
      </section>
      <section className="min-w-0 bg-ground">{planning ? <PlanPane /> : <Journey />}</section>
    </div>
  )
}

/* ---------------- thread ---------------- */

function Thread() {
  const { state } = useProject()
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [state.thread.length, state.thinking])

  return (
    <div className="thin-scroll flex-1 space-y-5 overflow-y-auto px-8 py-6">
      {state.thread.length === 0 && (
        <p className="max-w-[52ch] text-[14px] text-navy">What are you trying to do?</p>
      )}
      {state.thread.map((m) => (
        <Message key={m.id} msg={m} />
      ))}
      {state.thinking && (
        <div className="flex items-center gap-2 text-[13px] text-grey">
          <Spinner /> thinking…
        </div>
      )}
      <div ref={endRef} />
    </div>
  )
}

const TRIGGER_COPY: Record<string, string> = {
  excluded_large_stratum: 'A large group of sources was left out of the shortlist',
  excluded_user_nominated: "Something you named didn't make the shortlist",
  thin_base: 'The shortlist base is thin',
}
const triggerCopy = (trigger: string) => TRIGGER_COPY[trigger] ?? trigger.replace(/_/g, ' ')

const splitCsv = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)

function Message({ msg }: { msg: ThreadMsg }) {
  if (msg.role === 'user') {
    return (
      <div className="anim-rise flex justify-end">
        <div className="max-w-[80%] bg-blue px-4 py-2.5 text-[13.5px] leading-relaxed text-white">
          {msg.text}
        </div>
      </div>
    )
  }
  if (msg.checkin) return <CheckinBlock msg={msg} />
  return <p className="anim-rise max-w-[52ch] whitespace-pre-line text-[14px] leading-relaxed text-navy">{msg.text}</p>
}

function CheckinBlock({ msg }: { msg: ThreadMsg }) {
  const { answerCheckin } = useProject()
  const c = msg.checkin!
  const [openInput, setOpenInput] = useState<string | null>(null)
  const [budget, setBudget] = useState('')
  const [strata, setStrata] = useState('')
  const [docs, setDocs] = useState('')

  const submit = (optionId: string, params?: CheckinParams) => {
    setOpenInput(null)
    void answerCheckin(c.checkin_id, optionId, params)
  }

  const answeredLabel = c.reply ? (c.options.find((o) => o.id === c.reply)?.label ?? c.reply) : ''

  return (
    <div className="anim-glow border-l-[3px] border-orange bg-yellow-tint p-5">
      <PaneH className="mb-2">Check-in</PaneH>
      <p className="max-w-[52ch] text-[13.5px] leading-relaxed text-navy">{msg.text}</p>
      {!c.resolved && c.triggers.length > 0 && (
        <div className="mt-2 space-y-1">
          {c.triggers.map((t, i) => (
            <p key={i} className="text-[12px] text-orange-text">⚠ {triggerCopy(t.trigger)}</p>
          ))}
        </div>
      )}
      {c.resolved ? (
        <div className="mt-3 flex items-center gap-2 text-[12px] font-bold uppercase tracking-wide text-green-text">
          <Dot tone="done" /> Answered{answeredLabel ? ` — ${answeredLabel}` : ''}
        </div>
      ) : (
        <div className="mt-4 flex flex-col items-start gap-3">
          {c.options.map((opt) => (
            <div key={opt.id} className="w-full max-w-[52ch]">
              <button
                className={opt.id === 'abort' ? 'btn btn--ghost' : opt.id === 'continue' ? 'btn' : 'btn btn--sec'}
                title={opt.description}
                onClick={() => (opt.requires_user_input ? setOpenInput(openInput === opt.id ? null : opt.id) : submit(opt.id))}
              >
                {opt.label}
              </button>
              {opt.description && <p className="mt-1 text-[11.5px] text-grey">{opt.description}</p>}
              {opt.requires_user_input && openInput === opt.id && opt.id === 'adjust_budget' && (
                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="number"
                    className="h-8 w-28 border hairline px-2 text-[13px] text-navy outline-none focus:border-blue"
                    placeholder="Budget"
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                  />
                  <button
                    className="btn btn--sec !py-1 !text-[12px]"
                    disabled={!budget}
                    onClick={() => submit(opt.id, { budget: Number(budget) })}
                  >
                    Confirm
                  </button>
                </div>
              )}
              {opt.requires_user_input && openInput === opt.id && opt.id === 'deepen_clusters' && (
                <div className="mt-2 flex flex-col gap-2">
                  <input
                    className="h-8 border hairline px-2 text-[13px] text-navy outline-none focus:border-blue"
                    placeholder="Cluster ids, comma-separated"
                    value={strata}
                    onChange={(e) => setStrata(e.target.value)}
                  />
                  <input
                    className="h-8 border hairline px-2 text-[13px] text-navy outline-none focus:border-blue"
                    placeholder="Document ids, comma-separated"
                    value={docs}
                    onChange={(e) => setDocs(e.target.value)}
                  />
                  <button
                    className="btn btn--sec self-start !py-1 !text-[12px]"
                    disabled={!strata && !docs}
                    onClick={() => submit(opt.id, { strata: splitCsv(strata), docs: splitCsv(docs) })}
                  >
                    Confirm
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SuggestionChips() {
  const { state, sendChat } = useProject()
  if (state.phase === 'analysing' || state.suggestions.length === 0) return null
  return (
    <div className="flex flex-wrap gap-2 border-t hairline bg-white px-8 pt-4">
      {state.suggestions.map((s) => (
        <button key={s} className="chip chip--soft" onClick={() => void sendChat(s)}>
          {s}
        </button>
      ))}
    </div>
  )
}

function Composer() {
  const { sendChat, state } = useProject()
  const [text, setText] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const t = text.trim()
    if (!t || state.thinking) return
    setText('')
    void sendChat(t)
  }
  return (
    <form className="flex items-center gap-2 border-t hairline bg-white px-8 py-5" onSubmit={submit}>
      <input
        className="h-9 flex-1 border hairline bg-white px-3 text-[13.5px] text-navy outline-none placeholder:text-navy-40 focus:border-blue"
        placeholder="Reply to Policy Atlas…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        aria-label="Reply to Policy Atlas"
      />
      <button className="grid h-9 w-9 shrink-0 place-items-center bg-blue text-white transition-colors hover:bg-blue-hover" aria-label="Send">
        →
      </button>
    </form>
  )
}

/* ---------------- plan pane (planning phase) ---------------- */

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

function yearOf(iso: string): string {
  const m = /^(\d{4})/.exec(iso)
  return m ? m[1] : iso
}

function scopeChips(sc?: { published_after?: string | null; published_before?: string | null; publisher_country?: string | null } | null): string[] {
  if (!sc) return []
  const chips: string[] = []
  if (sc.published_after) chips.push(`Published after ${yearOf(sc.published_after)}`)
  if (sc.published_before) chips.push(`Published before ${yearOf(sc.published_before)}`)
  if (sc.publisher_country) chips.push(`Publisher country: ${sc.publisher_country}`)
  return chips
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <PaneH>{label}</PaneH>
      <div className="mt-2">{children}</div>
    </div>
  )
}

function PlanPane() {
  const { state, startAnalysis } = useProject()
  const [starting, setStarting] = useState(false)
  const plan = state.plan
  const steps = plan?.steps ?? []

  if (!plan || (!plan.question && steps.length === 0)) {
    return (
      <div className="flex h-full flex-col px-7 py-6">
        <PaneH>Plan</PaneH>
        <div className="flex flex-1 items-center justify-center">
          <p className="max-w-xs text-center text-sm text-grey">
            Forms here as you talk. Nothing runs until you approve it.
          </p>
        </div>
      </div>
    )
  }

  const scopingNotes = plan.scoping_notes ?? []
  const screeningCriteria = plan.screening_criteria ?? []
  const constraints = scopeChips(plan.scope_constraints)

  return (
    <div className="thin-scroll h-full space-y-5 overflow-y-auto px-7 py-6">
      <div>
        <div className="flex items-center justify-between">
          <PaneH>Plan</PaneH>
          <div className="flex items-center gap-2">
            {plan.time_band && <span className="text-[12px] text-grey">{plan.time_band}</span>}
            <span className={`chip ${plan.ready ? 'chip--green' : 'chip--soft'}`}>
              {plan.ready ? 'ready' : 'forming…'}
            </span>
          </div>
        </div>
        <p className="mt-1.5 text-[12.5px] text-grey">
          Agreed here before anything runs. The analysis follows it.
        </p>
      </div>

      <Field label="Question">
        <p className="text-[15px] font-semibold leading-snug text-navy">
          {plan.question ?? <span className="text-navy-40">Not set yet</span>}
        </p>
      </Field>

      {scopingNotes.length > 0 && (
        <Field label="Focus">
          <div className="flex flex-wrap gap-2">
            {scopingNotes.map((f) => (
              <span key={f} className="chip chip--soft">{f}</span>
            ))}
          </div>
          {screeningCriteria.length > 0 && (
            <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[12px] text-grey">
              {screeningCriteria.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </Field>
      )}

      {constraints.length > 0 && (
        <Field label="Constraints">
          <div className="flex flex-wrap gap-2">
            {constraints.map((c) => (
              <span key={c} className="chip chip--soft">{c}</span>
            ))}
          </div>
        </Field>
      )}

      {plan.search_effort && (
        <Field label="Search effort">
          <span className="text-sm font-medium text-navy">{label(SEARCH_EFFORT_LABEL, plan.search_effort)}</span>
        </Field>
      )}
      {plan.analysis_depth && (
        <Field label="Analysis depth">
          <span className="text-sm font-medium text-navy">{label(ANALYSIS_DEPTH_LABEL, plan.analysis_depth)}</span>
        </Field>
      )}
      {plan.backend_scope && (
        <Field label="Sources">
          <span className="text-sm font-medium text-navy">{SOURCES_LABEL[plan.backend_scope]}</span>
        </Field>
      )}
      {plan.steering_mode && (
        <Field label="Check-ins">
          <span className="text-sm font-medium text-navy">{label(STEERING_MODE_LABEL, plan.steering_mode)}</span>
        </Field>
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

      {plan.ready && (
        <div className="border-t hairline pt-5">
          <button
            className="btn w-full justify-center !py-3.5 !text-[14px]"
            disabled={starting}
            onClick={() => {
              setStarting(true)
              void startAnalysis()
            }}
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

/* ---------------- journey (analysing / complete) ---------------- */

function Journey() {
  const { state } = useProject()
  const { id } = useParams<{ id: string }>()
  const scrollRef = useRef<HTMLDivElement>(null)
  const complete = state.phase === 'complete'
  const aborted = state.phase === 'aborted'
  const searching = ['acquire', 'screen'].some((s) => state.stages[s]?.status === 'active')
  const hasLandscape = !!state.landscape && Object.keys(state.landscape.evidence_types).length > 0
  const hasGroups = !!state.groups && state.groups.facets.length > 0

  const jump = (sel: string) => {
    scrollRef.current?.querySelector(sel)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div ref={scrollRef} className="thin-scroll h-full overflow-y-auto px-7 py-6" style={{ scrollbarGutter: 'stable' }}>
      {state.phase === 'analysing' && <ProgressStrip />}
      <PlanRecap />

      <div className="sticky top-0 z-20 -mx-7 mb-4 flex gap-4 border-b hairline bg-ground/95 px-7 py-2 backdrop-blur-sm">
        {[
          ['#j-progress', 'Progress', true],
          ['#j-landscape', 'Landscape', hasLandscape],
          ['#j-findings', 'Findings', hasGroups],
          ['#j-coverage', 'Coverage', !!state.coverage],
        ].map(([sel, label, on]) => (
          <button
            key={String(label)}
            className={`text-[12px] font-bold uppercase tracking-wide ${on ? 'text-navy hover:text-blue' : 'cursor-default text-navy-20'}`}
            onClick={() => on && jump(String(sel))}
            disabled={!on}
          >
            {String(label)}
          </button>
        ))}
      </div>

      <h2 className="mb-4 font-display text-[20px] font-semibold text-navy">
        {complete ? 'Analysis complete' : aborted ? 'Analysis stopped' : state.phase === 'failed' ? 'Analysis stopped' : 'Analysing the evidence…'}
      </h2>
      {complete && state.completionStatus === 'degraded' && (
        <p className="mb-4 border-l-[3px] border-orange bg-orange-tint p-3 text-[13px] text-navy">
          Completed with some flagged events — recorded, not hidden. See the details below.
        </p>
      )}
      {aborted && (
        <p className="mb-4 border-l-[3px] border-orange bg-orange-tint p-3 text-[13px] text-navy">
          You stopped this run. Everything completed so far is kept below.
        </p>
      )}
      {state.phase === 'failed' && state.failure && (
        <p className="mb-4 border-l-[3px] border-orange bg-orange-tint p-3 text-[13px] text-navy">
          {state.failure}
        </p>
      )}

      <div className="space-y-5">
        {complete && <CompleteCard projectId={id!} />}

        <div id="j-progress" className="scroll-mt-14 space-y-5">
          {searching && <SearchCard />}
          {state.phase === 'analysing' && <ActivityCard />}
          <div className="card anim-rise">
            <PaneH className="mb-3">{complete || aborted ? 'How it got there' : 'The plan in motion'}</PaneH>
            <Timeline />
          </div>
          {state.funnel?.found != null && (
            <div className="card anim-rise">
              <PaneH className="mb-3">From sources to evidence</PaneH>
              <Funnel />
            </div>
          )}
          {(complete || aborted) && state.collation && (
            <div className="card anim-rise">
              <PaneH className="mb-2">Flagged events</PaneH>
              <pre className="thin-scroll max-h-40 overflow-auto whitespace-pre-wrap text-[12px] leading-relaxed text-navy">{state.collation}</pre>
            </div>
          )}
        </div>

        {hasLandscape && (
          <div id="j-landscape" className="scroll-mt-14">
            <Charts landscape={state.landscape!} />
          </div>
        )}

        {hasGroups && (
          <div id="j-findings" className="scroll-mt-14">
            <GroupsCard />
          </div>
        )}

        {state.coverage && (
          <div id="j-coverage" className="card anim-rise scroll-mt-14">
            <PaneH className="mb-2">Where I looked</PaneH>
            <div className="text-sm font-medium text-navy">
              {state.coverage.backends.map((b) => (b === 'openalex' ? 'OpenAlex' : b === 'overton' ? 'Overton' : b)).join(' · ')}
            </div>
            <p className="mt-1 text-[13px] text-navy">
              {state.coverage.summary ??
                (state.coverage.adequacy === 'adequate' ? 'Coverage judged adequate.' : 'Coverage judged thin — recorded, not hidden.')}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

function ProgressStrip() {
  const { state } = useProject()
  if (state.stageOrder.length === 0) return null
  return (
    <div className="mb-3">
      <div className="flex gap-1">
        {state.stageOrder.map((s) => {
          const st = state.stages[s]?.status
          return (
            <div
              key={s}
              className={`h-1 flex-1 ${
                st === 'done' ? 'bg-blue' : st === 'failed' ? 'bg-orange' : 'anim-breathe bg-blue'
              }`}
            />
          )
        })}
      </div>
      {state.paused && (
        <div className="mt-1 text-right text-[12px] font-semibold text-yellow-text">
          Paused — waiting on your answer
        </div>
      )}
    </div>
  )
}

function PlanRecap() {
  const { state } = useProject()
  const [open, setOpen] = useState(false)
  const plan = state.plan
  if (!plan?.question) return null
  const scopingNotes = plan.scoping_notes ?? []
  const screeningCriteria = plan.screening_criteria ?? []
  const constraints = scopeChips(plan.scope_constraints)
  const assumptions = plan.assumptions ?? []
  const steps = plan.steps ?? []
  // parity rule: everything the pre-run plan pane shows stays visible here
  const summary = [
    label(SEARCH_EFFORT_LABEL, plan.search_effort),
    label(ANALYSIS_DEPTH_LABEL, plan.analysis_depth),
    plan.backend_scope ? SOURCES_LABEL[plan.backend_scope] : '',
    plan.steering_mode ? `Check-ins: ${label(STEERING_MODE_LABEL, plan.steering_mode).toLowerCase()}` : '',
    plan.time_band ?? '',
  ].filter(Boolean).join(' · ')
  return (
    <div className="mb-3">
      <button className="chip chip--soft" onClick={() => setOpen(!open)} aria-expanded={open}>
        View plan {open ? '▴' : '▾'}
      </button>
      {open && (
        <div className="anim-rise mt-2 space-y-2 border hairline bg-white p-4 text-[13px]">
          <div className="font-semibold text-navy">{plan.question}</div>
          {(scopingNotes.length > 0 || constraints.length > 0) && (
            <div className="flex flex-wrap gap-1.5">
              {scopingNotes.map((f) => (
                <span key={f} className="chip chip--soft">{f}</span>
              ))}
              {constraints.map((c) => (
                <span key={c} className="chip chip--soft">{c}</span>
              ))}
            </div>
          )}
          {screeningCriteria.length > 0 && (
            <ul className="list-disc space-y-0.5 pl-4 text-[12px] text-grey">
              {screeningCriteria.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
          {summary && <div className="text-[12.5px] text-grey">{summary}</div>}
          {steps.length > 0 && (
            <div>
              <div className="text-[11px] font-bold uppercase tracking-wide text-navy-40">Agreed steps</div>
              <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-[12px] text-grey">
                {steps.map((s) => (
                  <li key={s.stage}>{s.label}</li>
                ))}
              </ol>
            </div>
          )}
          {assumptions.length > 0 && (
            <div>
              <div className="text-[11px] font-bold uppercase tracking-wide text-navy-40">Assumptions</div>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-[12px] text-grey">
                {assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Timeline() {
  const { state } = useProject()
  // execution order leads; un-run plan steps trail as pending
  const order = [...state.stageOrder]
  const seen = new Set(order)
  for (const s of state.plan?.steps ?? []) {
    if (!seen.has(s.stage)) {
      seen.add(s.stage)
      order.push(s.stage)
    }
  }
  const planned = new Map((state.plan?.steps ?? []).map((s) => [s.stage, s.label]))

  return (
    <ol className="space-y-2.5">
      {order.map((stage) => {
        const info: StageInfo | undefined = state.stages[stage]
        const label = info?.label ?? planned.get(stage) ?? stage
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
                    {info?.blurb || label}
                    {status === 'done' && secs != null && <div className="mt-1 text-grey">Took {formatElapsed(secs)}</div>}
                    {status === 'failed' && info?.reason && <div className="mt-1 text-orange-text">{info.reason}</div>}
                  </div>
                }
              >
                <span className={`font-medium ${status ? 'text-navy' : 'text-navy-40'}`}>{label}</span>
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
      {FUNNEL_DEFS.map(([key, label, def]) => {
        const v = f[key]
        if (v == null) return null
        return (
          <Tip key={String(key)} content={<div className="text-[12px] text-navy">{def}</div>} className="block">
            <div className="flex cursor-default items-center gap-3">
              <div className="w-44 shrink-0 text-right text-[12px] font-medium text-navy">{label}</div>
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
    <div className="card anim-rise">
      <PaneH className="mb-3">Searching</PaneH>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {backends.map(([key, label]) => {
          const b = state.search[key]
          return (
            <div key={key} className="border hairline p-3.5">
              <div className="flex items-baseline justify-between">
                <span className="text-[13px] font-bold text-navy">{label}</span>
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
            className={`truncate border-l-2 pl-2 text-[12.5px] ${
              i === lines.length - 1 ? 'border-blue text-navy' : 'border-transparent text-grey'
            }`}
          >
            {l.text}
            {l.count > 1 && <span className="ml-1 font-semibold text-navy">× {l.count}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

function GroupsCard() {
  const { state } = useProject()
  const facets = state.groups!.facets
  return (
    <div className="card anim-rise">
      <PaneH className="mb-3">Findings by group</PaneH>
      <div className="space-y-4">
        {facets.map((f) => {
          const top = [...f.groups].sort((a, b) => b.size - a.size).slice(0, 8)
          const hidden = f.groups.length - top.length
          const max = top[0]?.size ?? 1
          return (
            <div key={f.facet}>
              <div className="mb-1.5 text-[12px] font-bold uppercase tracking-wide text-navy-40">
                {f.facet.charAt(0).toUpperCase() + f.facet.slice(1)}
              </div>
              <div className="space-y-1">
                {top.map((grp) => (
                  <div key={grp.label} className="flex items-center gap-3">
                    <Tip content={<div className="text-[12px] text-navy">{grp.description}</div>} className="w-52 shrink-0">
                      <div className="cursor-default truncate text-right text-[12px] font-medium text-navy">{grp.label}</div>
                    </Tip>
                    <HBar value={grp.size} max={max} />
                    <span className="w-6 shrink-0 text-[12px] font-bold text-navy">{grp.size}</span>
                  </div>
                ))}
              </div>
              {hidden > 0 && <div className="mt-1 pl-[220px] text-[11px] text-grey">+ {hidden} smaller groups</div>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function CompleteCard({ projectId }: { projectId: string }) {
  const { state } = useProject()
  const included = state.funnel?.relevant
  const cited = state.funnel?.cited
  return (
    <div className="anim-rise border-l-[3px] border-green bg-white p-6 shadow-card ring-1 ring-line">
      <PaneH className="mb-2">Done</PaneH>
      <p className="max-w-[56ch] text-sm leading-relaxed text-navy">
        The evidence base is ready.{' '}
        {included != null && cited != null ? `${included} sources included, ${cited} cited — ` : ''}
        every claim traceable to its source, every exclusion recorded.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <Link to={`/project/${projectId}/evidence-base`} className="btn">Read the evidence base</Link>
        <Link to={`/project/${projectId}/sources`} className="btn btn--sec">All sources</Link>
      </div>
    </div>
  )
}
