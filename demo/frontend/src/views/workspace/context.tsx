// Workspace UI state: the artifact gallery, the right-pane view, and the
// IDE-style chat threads (each with its own multi-artifact context). Closing
// a thread archives it to the Chats library; reopen brings it back into the
// rail. The primary thread is wired to the real orchestrator via useProject;
// every other thread is a light local mock.

import {
  createContext, useCallback, useContext, useMemo, useState, type ReactNode,
} from 'react'
import { useProject } from '../../store'
import {
  CANNED, capabilityById, SEED_CHAT_HISTORY,
  type ArtifactRef, type CapabilityId, type MockArtifact,
} from './data'

const EVIDENCE_ID = 'evidence'
const PRIMARY_ID = 'primary'

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  text: string
}

export interface Thread {
  id: string
  title: string
  kind: 'primary' | 'mock'
  /** For mock threads: the artifact this job produces. */
  artifactId?: string
  updatedAt: string
  /** Higher = more recent — for sorting the Chats library. */
  sort: number
}

/** A row in the Chats library (open or archived). */
export interface ChatHistoryItem {
  id: string
  title: string
  kind: 'primary' | 'mock'
  artifactId?: string
  updatedAt: string
  sort: number
  preview: string
  open: boolean
  contextIds: string[]
}

export type RightView =
  | { mode: 'gallery' }
  | { mode: 'capabilities' }
  | { mode: 'detail'; artifactId: string }

interface WorkspaceStore {
  artifacts: ArtifactRef[]
  getArtifact(id: string): ArtifactRef | undefined
  view: RightView
  openGallery(): void
  openCapabilities(): void
  openArtifact(id: string): void
  startJob(capability: CapabilityId): void

  /** Currently open in the chat rail. */
  threads: Thread[]
  activeThreadId: string
  activeThread: Thread
  setActiveThread(id: string): void
  newChat(): void
  /** Archive from the rail (keeps history). */
  closeThread(id: string): void
  /** Open from the Chats library into the rail. */
  reopenChat(id: string): void
  /** Remove entirely from history. */
  deleteChat(id: string): void
  chatHistory: ChatHistoryItem[]
  mockMessages(threadId: string): ChatMessage[]
  sendToThread(threadId: string, text: string): void

  contextOf(threadId: string): string[]
  setThreadContext(threadId: string, ids: string[]): void

  /** Bumps when a chat should be focused (reopen / new) — Workspace expands. */
  chatFocusToken: number
}

const Ctx = createContext<WorkspaceStore | null>(null)

let seq = 1
const nid = () => seq++
let sortClock = 100

const seedMsgs: Record<string, ChatMessage[]> = {}
const seedContexts: Record<string, string[]> = { [PRIMARY_ID]: [] }
const seedArchived: Thread[] = SEED_CHAT_HISTORY.map((c) => {
  seedMsgs[c.id] = c.messages.map((m) => ({ id: nid(), role: m.role, text: m.text }))
  seedContexts[c.id] = c.contextIds
  return {
    id: c.id,
    title: c.title,
    kind: 'mock' as const,
    updatedAt: c.updatedAt,
    sort: c.sort,
  }
})

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { state } = useProject()

  const [mockArtifacts, setMockArtifacts] = useState<MockArtifact[]>([])

  const [evidenceStartedManual, setEvidenceStartedManual] = useState(false)
  const [view, setView] = useState<RightView>({ mode: 'gallery' })
  const [threads, setThreads] = useState<Thread[]>([
    { id: PRIMARY_ID, title: 'New chat', kind: 'primary', updatedAt: 'just now', sort: 50 },
  ])
  const [archived, setArchived] = useState<Thread[]>(seedArchived)
  const [activeThreadId, setActiveThreadId] = useState(PRIMARY_ID)
  const [mockMsgs, setMockMsgs] = useState<Record<string, ChatMessage[]>>(seedMsgs)
  const [contexts, setContexts] = useState<Record<string, string[]>>(seedContexts)
  const [chatFocusToken, setChatFocusToken] = useState(0)

  const evidenceStarted =
    evidenceStartedManual ||
    state.phase !== 'planning' ||
    !!state.plan?.question ||
    state.thread.length > 0 ||
    state.liveSections.length > 0

  const evidenceRef: ArtifactRef | null = useMemo(() => {
    if (!evidenceStarted) return null
    const status =
      state.phase === 'complete' ? 'complete'
      : state.phase === 'analysing' ? 'running'
      : 'draft'
    return {
      id: EVIDENCE_ID,
      capability: 'find_evidence',
      title: state.plan?.title || 'Evidence base',
      subtitle: state.plan?.question || 'Cited evidence base — forming as you steer the plan',
      status,
      updatedAt: status === 'complete' ? 'just now' : status === 'running' ? 'in progress' : 'draft',
      kind: 'evidence',
    }
  }, [evidenceStarted, state.phase, state.plan?.title, state.plan?.question])

  const artifacts: ArtifactRef[] = useMemo(() => {
    const mocks: ArtifactRef[] = mockArtifacts.map((m) => ({
      id: m.id,
      capability: m.capability,
      title: m.title,
      subtitle: m.subtitle,
      status: m.status,
      updatedAt: m.updatedAt,
      kind: 'mock',
      mock: m,
    }))
    return evidenceRef ? [evidenceRef, ...mocks] : mocks
  }, [evidenceRef, mockArtifacts])

  const getArtifact = useCallback(
    (id: string) => artifacts.find((a) => a.id === id),
    [artifacts],
  )

  const openGallery = useCallback(() => setView({ mode: 'gallery' }), [])
  const openCapabilities = useCallback(() => setView({ mode: 'capabilities' }), [])
  const openArtifact = useCallback((id: string) => setView({ mode: 'detail', artifactId: id }), [])

  const setActiveThread = useCallback((id: string) => setActiveThreadId(id), [])

  const setThreadContext = useCallback(
    (threadId: string, ids: string[]) =>
      setContexts((c) => ({ ...c, [threadId]: ids })),
    [],
  )

  const contextOf = useCallback(
    (threadId: string) => contexts[threadId] ?? [],
    [contexts],
  )

  const touch = (title?: string): Pick<Thread, 'updatedAt' | 'sort'> & { title?: string } => {
    sortClock += 1
    return { updatedAt: 'just now', sort: sortClock, ...(title ? { title } : {}) }
  }

  const newChat = useCallback(() => {
    const id = `chat-${nid()}`
    const seedCtx = view.mode === 'detail' ? [view.artifactId] : []
    const meta = touch()
    setThreads((t) => [...t, { id, title: 'New chat', kind: 'mock', ...meta }])
    setContexts((c) => ({ ...c, [id]: seedCtx }))
    setMockMsgs((m) => ({ ...m, [id]: [] }))
    setActiveThreadId(id)
    setChatFocusToken((n) => n + 1)
  }, [view])

  const closeThread = useCallback((id: string) => {
    setThreads((prev) => {
      const idx = prev.findIndex((t) => t.id === id)
      if (idx < 0) return prev
      const closing = prev[idx]!
      const next = prev.filter((t) => t.id !== id)
      setArchived((a) => [closing, ...a.filter((x) => x.id !== id)])
      if (next.length === 0) {
        const freshId = `chat-${nid()}`
        const meta = touch()
        setContexts((c) => ({ ...c, [freshId]: [] }))
        setMockMsgs((m) => ({ ...m, [freshId]: [] }))
        setActiveThreadId(freshId)
        return [{ id: freshId, title: 'New chat', kind: 'mock', ...meta }]
      }
      setActiveThreadId((active) => {
        if (active !== id) return active
        return next[Math.min(idx, next.length - 1)]!.id
      })
      return next
    })
  }, [])

  const reopenChat = useCallback((id: string) => {
    setArchived((a) => {
      const found = a.find((t) => t.id === id)
      if (!found) return a
      setThreads((t) => (t.some((x) => x.id === id) ? t : [...t, { ...found, ...touch() }]))
      return a.filter((t) => t.id !== id)
    })
    setActiveThreadId(id)
    setChatFocusToken((n) => n + 1)
  }, [])

  const deleteChat = useCallback((id: string) => {
    if (id === PRIMARY_ID) return
    setThreads((t) => {
      const next = t.filter((x) => x.id !== id)
      if (next.length === 0) {
        const freshId = `chat-${nid()}`
        const meta = touch()
        setContexts((c) => {
          const { [id]: _, ...rest } = c
          return { ...rest, [freshId]: [] }
        })
        setMockMsgs((m) => {
          const { [id]: _, ...rest } = m
          return { ...rest, [freshId]: [] }
        })
        setActiveThreadId(freshId)
        return [{ id: freshId, title: 'New chat', kind: 'mock', ...meta }]
      }
      setActiveThreadId((active) => (active === id ? next[0]!.id : active))
      setContexts((c) => {
        const { [id]: _, ...rest } = c
        return rest
      })
      setMockMsgs((m) => {
        const { [id]: _, ...rest } = m
        return rest
      })
      return next
    })
    setArchived((a) => a.filter((x) => x.id !== id))
  }, [])

  const startJob = useCallback(
    (capability: CapabilityId) => {
      if (capability === 'find_evidence') {
        setEvidenceStartedManual(true)
        setArchived((a) => a.filter((x) => x.id !== PRIMARY_ID))
        setThreads((t) => {
          const meta = touch()
          if (t.some((x) => x.id === PRIMARY_ID)) {
            return t.map((x) =>
              x.id === PRIMARY_ID
                ? { ...x, title: 'Evidence base', kind: 'primary', artifactId: EVIDENCE_ID, ...meta }
                : x,
            )
          }
          return [
            { id: PRIMARY_ID, title: 'Evidence base', kind: 'primary', artifactId: EVIDENCE_ID, ...meta },
            ...t,
          ]
        })
        setContexts((c) => ({ ...c, [PRIMARY_ID]: [EVIDENCE_ID] }))
        setActiveThreadId(PRIMARY_ID)
        setView({ mode: 'detail', artifactId: EVIDENCE_ID })
        setChatFocusToken((n) => n + 1)
        return
      }
      const cap = capabilityById(capability)
      const canned = CANNED[capability]
      const artifactId = `mock-${nid()}`
      const artifact: MockArtifact = {
        id: artifactId,
        capability,
        title: `${cap.title} — draft`,
        subtitle: canned.subtitle,
        status: 'draft',
        updatedAt: 'just now',
        output: [],
        activity: [{ at: 'now', text: `Job started — ${cap.title}` }],
      }
      setMockArtifacts((a) => [artifact, ...a])

      // Reuse the active blank "New chat" tab when possible; otherwise open a new one
      const reusable = threads.find(
        (t) => t.id === activeThreadId && t.title === 'New chat' && t.kind === 'mock',
      )
      const threadId = reusable?.id ?? `chat-${nid()}`
      const meta = touch()
      setThreads((t) => {
        if (reusable) {
          return t.map((x) =>
            x.id === threadId ? { ...x, title: cap.title, artifactId, ...meta } : x,
          )
        }
        return [...t, { id: threadId, title: cap.title, kind: 'mock', artifactId, ...meta }]
      })
      setContexts((c) => ({ ...c, [threadId]: [artifactId] }))
      setMockMsgs((m) => ({
        ...m,
        [threadId]: [{ id: nid(), role: 'assistant', text: canned.greeting }],
      }))
      setActiveThreadId(threadId)
      setView({ mode: 'detail', artifactId })
      setChatFocusToken((n) => n + 1)
    },
    [threads, activeThreadId],
  )

  const sendToThread = useCallback(
    (threadId: string, text: string) => {
      setMockMsgs((m) => ({
        ...m,
        [threadId]: [...(m[threadId] ?? []), { id: nid(), role: 'user', text }],
      }))
      setThreads((t) => t.map((x) => (x.id === threadId ? { ...x, ...touch() } : x)))
      const thread = threads.find((t) => t.id === threadId) ?? archived.find((t) => t.id === threadId)
      const artifactId = thread?.artifactId
      const artifact = artifactId ? mockArtifacts.find((a) => a.id === artifactId) : undefined
      const reply = artifact ? CANNED[artifact.capability].reply : 'Noted — this is a mocked assistant for the demo.'

      window.setTimeout(() => {
        setMockMsgs((m) => ({
          ...m,
          [threadId]: [...(m[threadId] ?? []), { id: nid(), role: 'assistant', text: reply }],
        }))
        if (artifact && artifact.status === 'draft') {
          const cap = capabilityById(artifact.capability)
          const canned = CANNED[artifact.capability]
          setMockArtifacts((all) =>
            all.map((a) =>
              a.id === artifact.id
                ? {
                    ...a,
                    status: 'complete',
                    title: cap.title,
                    output: canned.output,
                    updatedAt: 'just now',
                    activity: [
                      ...a.activity,
                      { at: 'now', text: 'Scope confirmed' },
                      { at: 'now', text: `${cap.title} complete` },
                    ],
                  }
                : a,
            ),
          )
          setThreads((t) => t.map((x) => (x.id === threadId ? { ...x, title: cap.title, ...touch() } : x)))
        }
      }, 650)
    },
    [threads, archived, mockArtifacts],
  )

  const previewOf = useCallback(
    (id: string, kind: Thread['kind']): string => {
      if (kind === 'primary') {
        const last = state.thread[state.thread.length - 1]
        return last?.text ?? 'Orchestrator conversation for the evidence base.'
      }
      const msgs = mockMsgs[id] ?? []
      const last = msgs[msgs.length - 1]
      return last?.text ?? 'Empty chat.'
    },
    [state.thread, mockMsgs],
  )

  const chatHistory: ChatHistoryItem[] = useMemo(() => {
    const openIds = new Set(threads.map((t) => t.id))
    const all = [...threads, ...archived.filter((a) => !openIds.has(a.id))]
    return all
      .map((t) => ({
        id: t.id,
        title: t.title,
        kind: t.kind,
        artifactId: t.artifactId,
        updatedAt: t.updatedAt,
        sort: t.sort,
        preview: previewOf(t.id, t.kind),
        open: openIds.has(t.id),
        contextIds: contexts[t.id] ?? [],
      }))
      .sort((a, b) => b.sort - a.sort)
  }, [threads, archived, previewOf, contexts])

  const activeThread = threads.find((t) => t.id === activeThreadId) ?? threads[0]

  const store = useMemo<WorkspaceStore>(
    () => ({
      artifacts, getArtifact, view, openGallery, openCapabilities, openArtifact, startJob,
      threads, activeThreadId, activeThread, setActiveThread, newChat, closeThread,
      reopenChat, deleteChat, chatHistory,
      mockMessages: (id: string) => mockMsgs[id] ?? [],
      sendToThread, contextOf, setThreadContext, chatFocusToken,
    }),
    [
      artifacts, getArtifact, view, openGallery, openCapabilities, openArtifact, startJob,
      threads, activeThreadId, activeThread, setActiveThread, newChat, closeThread,
      reopenChat, deleteChat, chatHistory, mockMsgs,
      sendToThread, contextOf, setThreadContext, chatFocusToken,
    ],
  )

  return <Ctx.Provider value={store}>{children}</Ctx.Provider>
}

export function useWorkspace(): WorkspaceStore {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useWorkspace outside WorkspaceProvider')
  return ctx
}
