// The chat column: IDE-style thread switcher, per-thread multi-artifact
// context, and the message stream. The primary thread is the real
// orchestrator (useProject); mock threads are local.

import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { CheckinParams } from '../../api'
import { useProject, type ThreadMsg } from '../../store'
import { Dot, PaneH, Spinner } from '../../ui'
import { useWorkspace } from './context'

export default function ChatPanel({ onCollapse }: { onCollapse: () => void }) {
  const ws = useWorkspace()
  const { state, sendChat } = useProject()
  const active = ws.activeThread

  const onSend = (text: string) => {
    if (active.kind === 'primary') void sendChat(text)
    else ws.sendToThread(active.id, text)
  }

  return (
    <div className="flex h-full min-w-0 flex-col bg-white">
      <ThreadBar onCollapse={onCollapse} />
      {active.kind === 'primary' ? <PrimaryThread /> : <MockThread threadId={active.id} />}
      <ContextBar threadId={active.id} />
      <Composer onSend={onSend} disabled={active.kind === 'primary' && state.thinking} />
    </div>
  )
}

/* ---------------- thread bar ---------------- */

function ThreadBar({ onCollapse }: { onCollapse: () => void }) {
  const ws = useWorkspace()
  return (
    <div className="flex items-center gap-1 border-b hairline px-2 py-1.5">
      <button
        className="grid h-7 w-7 shrink-0 place-items-center text-grey hover:text-navy"
        onClick={onCollapse}
        title="Collapse chat"
        aria-label="Collapse chat"
      >
        «
      </button>
      <div className="thin-scroll flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
        {ws.threads.map((t) => {
          const active = t.id === ws.activeThreadId
          return (
            <div
              key={t.id}
              className={`group flex shrink-0 items-center border ${
                active
                  ? 'border-blue-edge bg-blue-tint text-blue'
                  : 'border-transparent text-grey hover:text-navy'
              }`}
            >
              <button
                className="whitespace-nowrap py-1 pl-2.5 pr-1 text-[12px] font-semibold"
                onClick={() => ws.setActiveThread(t.id)}
              >
                {t.title}
              </button>
              <button
                className={`grid h-6 w-6 place-items-center text-[11px] transition-opacity ${
                  active ? 'opacity-70 hover:opacity-100' : 'opacity-0 group-hover:opacity-70 hover:!opacity-100'
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  ws.closeThread(t.id)
                }}
                title="Close chat"
                aria-label={`Close ${t.title}`}
              >
                ✕
              </button>
            </div>
          )
        })}
      </div>
      <button
        className="grid h-7 w-7 shrink-0 place-items-center text-[16px] text-grey hover:text-navy"
        onClick={ws.newChat}
        title="New chat"
        aria-label="New chat"
      >
        +
      </button>
    </div>
  )
}

/* ---------------- context bar ---------------- */

function ContextBar({ threadId }: { threadId: string }) {
  const ws = useWorkspace()
  const navigate = useNavigate()
  const { id: projectId } = useParams<{ id: string }>()
  const [open, setOpen] = useState(false)
  const ids = ws.contextOf(threadId)
  const inContext = ids.map((id) => ws.getArtifact(id)).filter(Boolean)

  const toggle = (id: string) => {
    const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
    ws.setThreadContext(threadId, next)
  }

  const goToArtifact = (artifactId: string) => {
    ws.openArtifact(artifactId)
    navigate(`/project/${projectId}`)
  }

  return (
    <div className="relative flex flex-wrap items-center gap-1.5 border-t hairline px-3 py-2">
      <span className="text-[10.5px] font-extrabold uppercase tracking-[.06em] text-navy-40">Context</span>
      {inContext.length === 0 && <span className="text-[12px] text-grey">Whole project</span>}
      {inContext.map((a) => (
        <span key={a!.id} className="chip chip--blue !gap-0.5 !py-0.5">
          <button
            type="button"
            className="max-w-[140px] truncate hover:underline"
            title={`Open ${a!.title}`}
            onClick={() => goToArtifact(a!.id)}
          >
            {a!.title}
          </button>
          <button
            type="button"
            className="text-blue hover:text-navy"
            onClick={() => toggle(a!.id)}
            aria-label="Remove from context"
          >
            ✕
          </button>
        </span>
      ))}
      <button className="chip !py-0.5 text-grey hover:text-navy" onClick={() => setOpen((o) => !o)}>
        @ Add context
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} aria-hidden />
          <div className="absolute bottom-full left-3 z-20 mb-1 w-72 border border-line-2 bg-white p-2 shadow-panel">
            <PaneH className="mb-1.5 px-1">Add artifacts to this chat</PaneH>
            {ws.artifacts.length === 0 && (
              <p className="px-1 py-2 text-[12px] text-grey">No artifacts yet.</p>
            )}
            {ws.artifacts.map((a) => (
              <label
                key={a.id}
                className="flex cursor-pointer items-center gap-2 px-1 py-1.5 text-[12.5px] text-navy hover:bg-ground"
              >
                <input type="checkbox" checked={ids.includes(a.id)} onChange={() => toggle(a.id)} />
                <span className="min-w-0 flex-1 truncate">{a.title}</span>
              </label>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

/* ---------------- primary (real orchestrator) thread ---------------- */

function PrimaryThread() {
  const { state, sendChat } = useProject()
  const ws = useWorkspace()
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [state.thread.length, state.thinking])

  return (
    <>
      <div className="thin-scroll flex-1 space-y-5 overflow-y-auto px-6 py-6">
        {state.thread.length === 0 && (
          <p className="max-w-[52ch] text-[14px] text-navy">
            Tell me what you'd like to do — or choose a{' '}
            <button
              type="button"
              className="font-semibold text-blue underline underline-offset-2 hover:text-blue-hover"
              onClick={ws.openCapabilities}
            >
              new job
            </button>
            .
          </p>
        )}
        {state.thread.map((m) => (
          <Message key={m.id} msg={m} />
        ))}
        {state.thinking && (
          <div className="flex items-center gap-2 text-[13px] text-grey">
            <Spinner /> {state.plannerProgress ?? 'thinking…'}
          </div>
        )}
        <div ref={endRef} />
      </div>
      {state.phase !== 'analysing' && state.suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t hairline px-6 pt-4">
          {state.suggestions.map((s) => (
            <button key={s} className="chip chip--soft" onClick={() => void sendChat(s)}>
              {s}
            </button>
          ))}
        </div>
      )}
    </>
  )
}

/* ---------------- mock thread ---------------- */

function MockThread({ threadId }: { threadId: string }) {
  const ws = useWorkspace()
  const messages = ws.mockMessages(threadId)
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length])

  return (
    <div className="thin-scroll flex-1 space-y-5 overflow-y-auto px-6 py-6">
      {messages.length === 0 && (
        <p className="max-w-[52ch] text-[14px] text-navy">
          What would you like to work on? Add an artifact to the context below to ground the chat.
        </p>
      )}
      {messages.map((m) =>
        m.role === 'user' ? (
          <div key={m.id} className="anim-rise flex justify-end">
            <div className="max-w-[80%] bg-blue px-4 py-2.5 text-[13.5px] leading-relaxed text-white">{m.text}</div>
          </div>
        ) : (
          <p key={m.id} className="anim-rise max-w-[52ch] whitespace-pre-line text-[14px] leading-relaxed text-navy">
            {m.text}
          </p>
        ),
      )}
      <div ref={endRef} />
    </div>
  )
}

/* ---------------- composer ---------------- */

function Composer({ onSend, disabled = false }: { onSend: (text: string) => void; disabled?: boolean }) {
  const [text, setText] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    const t = text.trim()
    if (!t || disabled) return
    setText('')
    onSend(t)
  }
  return (
    <form className="flex items-center gap-2 px-6 pb-4 pt-1" onSubmit={submit}>
      <input
        className="h-9 flex-1 border hairline bg-white px-3 text-[13.5px] text-navy outline-none placeholder:text-navy-40 focus:border-blue"
        placeholder="Reply to Policy Atlas…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        aria-label="Reply to Policy Atlas"
      />
      <button
        className="grid h-9 w-9 shrink-0 place-items-center bg-blue text-white transition-colors hover:bg-blue-hover"
        aria-label="Send"
      >
        →
      </button>
    </form>
  )
}

/* ---------------- message + check-in (primary thread) ---------------- */

const TRIGGER_COPY: Record<string, string> = {
  excluded_large_stratum: 'A large group of sources was left out of the shortlist',
  excluded_user_nominated: "Something you named didn't make the shortlist",
  thin_base: 'The shortlist base is thin',
}
const triggerCopy = (trigger: string) => TRIGGER_COPY[trigger] ?? trigger.replace(/_/g, ' ')
const splitCsv = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)
const MODES = ['frequent', 'moderate', 'minimal', 'unattended'] as const

function Message({ msg }: { msg: ThreadMsg }) {
  if (msg.role === 'user') {
    return (
      <div className="anim-rise flex justify-end">
        <div className="max-w-[80%] bg-blue px-4 py-2.5 text-[13.5px] leading-relaxed text-white">{msg.text}</div>
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
  const [freeText, setFreeText] = useState('')

  const submit = (optionId: string, params?: CheckinParams) => {
    setOpenInput(null)
    void answerCheckin(c.checkin_id, optionId, params)
  }

  const chosen = c.reply ? c.options.find((o) => o.id === c.reply) : undefined
  const rp = (c.replyParams ?? {}) as {
    text?: string; budget?: number; mode?: string; strata?: string[]; docs?: string[]
  }
  const answeredLabel = c.reply === 'free_text' ? 'In your own words' : (chosen?.label ?? c.reply ?? '')
  const answeredDetail =
    c.reply === 'free_text'
      ? (rp.text ? `“${rp.text}”` : '')
      : [
          chosen?.description ?? '',
          rp.budget != null ? `Budget → ${rp.budget}` : '',
          rp.mode ? `Mode → ${rp.mode}` : '',
          rp.strata?.length ? `Clusters: ${rp.strata.join(', ')}` : '',
          rp.docs?.length ? `Documents: ${rp.docs.join(', ')}` : '',
        ].filter(Boolean).join(' · ')

  return (
    <div className="anim-glow border-l-[3px] border-orange bg-yellow-tint p-5">
      <PaneH className="mb-2">{c.kind === 'confirm' ? 'Confirm steering' : 'Check-in'}</PaneH>
      <p className="max-w-[52ch] text-[13.5px] leading-relaxed text-navy">{msg.text}</p>
      {c.kind === 'confirm' && c.render && (
        <pre className="mt-2 max-h-64 max-w-[52ch] overflow-auto whitespace-pre-wrap border hairline bg-white p-3 text-[12px] leading-relaxed text-navy">
          {c.render}
        </pre>
      )}
      {!c.resolved && c.triggers.length > 0 && (
        <div className="mt-2 space-y-1">
          {c.triggers.map((t, i) => (
            <p key={i} className="text-[12px] text-orange-text">⚠ {triggerCopy(t.trigger)}</p>
          ))}
        </div>
      )}
      {c.resolved ? (
        <div className="mt-3">
          <div className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-wide text-green-text">
            <Dot tone="done" /> Answered
          </div>
          {answeredLabel && (
            <div className="mt-2 max-w-[52ch] border-l-2 border-line-2 bg-white px-3 py-2">
              <p className="text-[13px] font-bold text-navy">{answeredLabel}</p>
              {answeredDetail && <p className="mt-0.5 text-[12px] text-grey">{answeredDetail}</p>}
            </div>
          )}
        </div>
      ) : (
        <div className="mt-4 flex flex-col items-start gap-3">
          {c.options.map((opt) => (
            <div key={opt.id} className="w-full max-w-[52ch]">
              {opt.suggested && (
                <p className="mb-0.5 text-[10.5px] font-bold uppercase tracking-wide text-blue">
                  Suggested by the orchestrator
                </p>
              )}
              <button
                className={opt.id === 'abort' ? 'btn btn--ghost' : opt.id === 'continue' || opt.id === 'apply' ? 'btn' : 'btn btn--sec'}
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
              {opt.requires_user_input && openInput === opt.id && opt.id === 'change_mode' && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {MODES.map((m) => (
                    <button key={m} className="btn btn--sec !py-1 !text-[12px]" onClick={() => submit(opt.id, { mode: m })}>
                      {m}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          {c.kind !== 'confirm' && (
            <div className="w-full max-w-[52ch] border-t hairline pt-3">
              <p className="mb-1.5 text-[11.5px] text-grey">
                Or steer in your own words — you'll see exactly what it means before anything applies.
              </p>
              <div className="flex items-end gap-2">
                <textarea
                  className="min-h-[56px] flex-1 border hairline px-2 py-1.5 text-[13px] leading-relaxed text-navy outline-none focus:border-blue"
                  placeholder="e.g. Drop anything before 2015, and add a section on costs"
                  value={freeText}
                  onChange={(e) => setFreeText(e.target.value)}
                />
                <button
                  className="btn btn--sec !py-1 !text-[12px]"
                  disabled={!freeText.trim()}
                  onClick={() => submit('free_text', { text: freeText.trim() })}
                >
                  Steer
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
