// Project store: one SSE stream in, one reducer, read-models refetched as
// stages land. The backlog replays in full on (re)connect, so every piece of
// state here must rebuild idempotently from events alone.

import {
  createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef,
  type ReactNode,
} from 'react'
import { api } from './api'
import type {
  CheckinOption, CheckinParams, CheckinTrigger, Coverage, DemoEvent, Funnel, Groups,
  Landscape, Plan, ProgressData,
} from './api'

export type Phase = 'planning' | 'analysing' | 'complete' | 'failed' | 'aborted'

export interface ThreadMsg {
  id: number
  role: 'user' | 'assistant'
  text: string
  checkin?: {
    checkin_id: string
    kind: 'steer_point' | 'check_in'
    render: string
    options: CheckinOption[]
    triggers: CheckinTrigger[]
    resolved: boolean
    reply?: string
  }
}

export interface StageInfo {
  stage: string
  label: string
  blurb: string
  status: 'active' | 'done' | 'failed'
  summary?: Record<string, number>
  reason?: string
  skipped?: boolean
}

export interface ActivityLine {
  id: number
  text: string
  count: number
}

interface State {
  phase: Phase
  plan: Plan | null
  thread: ThreadMsg[]
  thinking: boolean
  stages: Record<string, StageInfo>
  stageOrder: string[]
  activity: ActivityLine[]
  search: Record<string, { queries: string[]; results: number }>
  paused: boolean
  funnel: Funnel | null
  landscape: Landscape | null
  groups: Groups | null
  coverage: Coverage | null
  failure: string | null
  completionStatus: 'succeeded' | 'degraded' | null
  collation: string | null
  suggestions: string[]
}

const initial: State = {
  phase: 'planning', plan: null, thread: [], thinking: false,
  stages: {}, stageOrder: [], activity: [], search: {}, paused: false,
  funnel: null, landscape: null, groups: null, coverage: null, failure: null,
  completionStatus: null, collation: null, suggestions: [],
}

let seq = 1
const nid = () => seq++

type Action =
  | { type: 'sse'; event: DemoEvent }
  | { type: 'reset' }
  | { type: 'user.sent'; text: string }
  | { type: 'thinking'; on: boolean }
  | { type: 'checkin.answered'; checkinId: string; reply: string }
  | { type: 'data'; key: 'funnel' | 'landscape' | 'groups' | 'coverage' | 'plan'; value: unknown }

function progressLine(d: ProgressData): string | null {
  if (d.kind === 'search_query' && d.query) return `→ ${title(d.backend)}: “${d.query}”`
  if (d.kind === 'results' && d.count != null) return `← ${title(d.backend)}: ${d.count} results`
  if (d.kind === 'round') return `Search round ${d.round ?? 2}: ${d.new_relevant ?? '?'} newly relevant (${d.total_relevant ?? '?'} total)`
  if (d.note) return String(d.note)
  return null
}

const title = (b?: string) => (b === 'openalex' ? 'OpenAlex' : b === 'overton' ? 'Overton' : (b ?? ''))

function isDuplicateMsg(thread: ThreadMsg[], role: ThreadMsg['role'], text: string): boolean {
  return thread.slice(-6).some((m) => m.role === role && m.text === text)
}

function reduce(state: State, action: Action): State {
  switch (action.type) {
    case 'reset':
      // SSE reconnect: the backlog replays everything — drop stream-derived
      // state, keep fetched read-models (they refetch on the next completion)
      return { ...state, thread: [], stages: {}, stageOrder: [], activity: [], search: {}, paused: false }
    case 'user.sent':
      return {
        ...state, thinking: true, suggestions: [],
        thread: [...state.thread, { id: nid(), role: 'user', text: action.text }],
      }
    case 'thinking':
      return { ...state, thinking: action.on }
    case 'checkin.answered':
      return {
        ...state,
        paused: false,
        thread: state.thread.map((m) =>
          m.checkin?.checkin_id === action.checkinId
            ? { ...m, checkin: { ...m.checkin, resolved: true, reply: action.reply } }
            : m,
        ),
      }
    case 'data':
      return { ...state, [action.key]: action.value }
    case 'sse':
      return onEvent(state, action.event)
  }
}

function onEvent(state: State, ev: DemoEvent): State {
  switch (ev.type) {
    case 'plan.updated':
      return { ...state, plan: ev.data.plan, thinking: false }
    case 'user.message':
      if (isDuplicateMsg(state.thread, 'user', ev.data.text)) return state
      return { ...state, thread: [...state.thread, { id: nid(), role: 'user', text: ev.data.text }] }
    case 'narration':
      if (isDuplicateMsg(state.thread, 'assistant', ev.data.text)) return state
      return {
        ...state, thinking: false,
        thread: [...state.thread, { id: nid(), role: 'assistant', text: ev.data.text }],
        suggestions: ev.data.suggestions ?? state.suggestions,
      }
    case 'analysis.started':
      return { ...state, phase: 'analysing', suggestions: [] }
    case 'analysis.completed':
      return {
        ...state, phase: 'complete', paused: false,
        completionStatus: ev.data.status, collation: ev.data.collation,
      }
    case 'analysis.failed':
      return {
        ...state, phase: 'failed', paused: false, failure: ev.data.message,
        collation: ev.data.collation ?? state.collation,
      }
    case 'analysis.aborted':
      return { ...state, phase: 'aborted', paused: false, collation: ev.data.collation }
    case 'checkin': {
      if (state.thread.some((m) => m.checkin?.checkin_id === ev.data.checkin_id)) return state
      return {
        ...state, paused: true,
        thread: [...state.thread, {
          id: nid(), role: 'assistant', text: ev.data.text,
          checkin: {
            checkin_id: ev.data.checkin_id, kind: ev.data.kind, render: ev.data.render,
            options: ev.data.options, triggers: ev.data.triggers, resolved: false,
          },
        }],
      }
    }
    case 'checkin.resolved':
      return reduce(state, { type: 'checkin.answered', checkinId: ev.data.checkin_id, reply: ev.data.reply })
    case 'stage.started': {
      const { stage, stage_label, stage_blurb } = ev.data
      const known = state.stages[stage]
      return {
        ...state,
        phase: state.phase === 'planning' ? 'analysing' : state.phase,
        stageOrder: known ? state.stageOrder : [...state.stageOrder, stage],
        stages: {
          ...state.stages,
          [stage]: { stage, label: stage_label, blurb: stage_blurb, status: known?.status === 'done' ? 'done' : 'active', summary: known?.summary },
        },
      }
    }
    case 'stage.completed': {
      const { stage, stage_label, summary } = ev.data
      return {
        ...state,
        stageOrder: state.stages[stage] ? state.stageOrder : [...state.stageOrder, stage],
        stages: {
          ...state.stages,
          [stage]: { stage, label: stage_label, blurb: state.stages[stage]?.blurb ?? '', status: 'done', summary },
        },
      }
    }
    case 'stage.failed': {
      const { stage, stage_label, reason, skipped } = ev.data
      // non-fatal: mark this timeline row failed, the run continues off other predecessors
      return {
        ...state,
        stageOrder: state.stages[stage] ? state.stageOrder : [...state.stageOrder, stage],
        stages: {
          ...state.stages,
          [stage]: { stage, label: stage_label, blurb: state.stages[stage]?.blurb ?? '', status: 'failed', reason, skipped },
        },
      }
    }
    case 'stage.progress': {
      const d = ev.data
      const line = progressLine(d)
      // collapse consecutive identical lines AT INGEST with a true count —
      // collapsing later, after the buffer cap, would under-count long stages
      let activity = state.activity
      if (line) {
        const last = activity[activity.length - 1]
        activity = last && last.text === line
          ? [...activity.slice(0, -1), { ...last, count: last.count + 1 }]
          : [...activity.slice(-40), { id: nid(), text: line, count: 1 }]
      }
      let search = state.search
      if (d.kind === 'search_query' && d.backend && d.query) {
        const b = search[d.backend] ?? { queries: [], results: 0 }
        search = { ...search, [d.backend]: { ...b, queries: [...b.queries.slice(-4), d.query] } }
      }
      if (d.kind === 'results' && d.backend && d.count != null) {
        const b = search[d.backend] ?? { queries: [], results: 0 }
        search = { ...search, [d.backend]: { ...b, results: b.results + d.count } }
      }
      return { ...state, activity, search }
    }
  }
}

interface Store {
  state: State
  sendChat(text: string): Promise<void>
  startAnalysis(): Promise<void>
  answerCheckin(checkinId: string, reply: string, params?: CheckinParams): Promise<void>
}

const Ctx = createContext<Store | null>(null)

export function ProjectProvider({ projectId, children }: { projectId: string; children: ReactNode }) {
  const [state, dispatch] = useReducer(reduce, initial)
  const idRef = useRef(projectId)
  idRef.current = projectId

  const refetch = useCallback((which: 'funnel' | 'landscape' | 'groups' | 'coverage') => {
    const id = idRef.current
    const fns = {
      funnel: api.getFunnel, landscape: api.getLandscape,
      groups: api.getGroups, coverage: api.getCoverage,
    } as const
    fns[which](id)
      .then((value) => dispatch({ type: 'data', key: which, value }))
      .catch(() => {})
  }, [])

  useEffect(() => {
    api.getPlan(projectId).then((plan) => dispatch({ type: 'data', key: 'plan', value: plan })).catch(() => {})
    refetch('funnel'); refetch('landscape'); refetch('groups'); refetch('coverage')

    const handle = api.openEvents(
      projectId,
      (event) => {
        dispatch({ type: 'sse', event })
        if (event.type === 'stage.completed') {
          refetch('funnel')
          if (event.data.stage === 'characterise') refetch('landscape')
          if (event.data.stage === 'group') refetch('groups')
          if (event.data.stage === 'screen' || event.data.stage === 'deep_search') refetch('coverage')
        }
        if (event.type === 'analysis.completed') {
          refetch('funnel'); refetch('landscape'); refetch('groups'); refetch('coverage')
        }
      },
      () => dispatch({ type: 'reset' }),
    )
    return () => handle.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  // long live stages move the funnel mid-stage: poll while analysing
  const analysing = state.phase === 'analysing'
  useEffect(() => {
    if (!analysing) return
    const t = setInterval(() => refetch('funnel'), 10_000)
    return () => clearInterval(t)
  }, [analysing, refetch])

  const sendChat = useCallback(async (text: string) => {
    dispatch({ type: 'user.sent', text })
    try {
      const { reply, plan, suggestions } = await api.chat(idRef.current, text)
      dispatch({ type: 'sse', event: { type: 'narration', data: { text: reply, suggestions } } })
      dispatch({ type: 'data', key: 'plan', value: plan })
    } catch {
      dispatch({ type: 'thinking', on: false })
      dispatch({
        type: 'sse',
        event: { type: 'narration', data: { text: 'Something went wrong reaching the orchestrator — try that again.' } },
      })
    }
  }, [])

  const startAnalysis = useCallback(async () => {
    await api.start(idRef.current)
  }, [])

  const answerCheckin = useCallback(async (checkinId: string, reply: string, params?: CheckinParams) => {
    dispatch({ type: 'checkin.answered', checkinId, reply })
    await api.answerCheckin(idRef.current, checkinId, reply, params)
  }, [])

  const store = useMemo(
    () => ({ state, sendChat, startAnalysis, answerCheckin }),
    [state, sendChat, startAnalysis, answerCheckin],
  )
  return <Ctx.Provider value={store}>{children}</Ctx.Provider>
}

export function useProject(): Store {
  const store = useContext(Ctx)
  if (!store) throw new Error('useProject outside ProjectProvider')
  return store
}
