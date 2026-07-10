// Live REST + SSE client. The vite dev server proxies /api to the FastAPI backend.

import type { DemoApi, DemoEvent } from './types'
import { EVENT_TYPES } from './types'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`)
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${path}`)
  return res.json() as Promise<T>
}

export const liveApi: DemoApi = {
  listProjects: () => get('/projects'),
  createProject: (name) => post('/projects', { name }),
  chat: (id, message) => post(`/projects/${id}/chat`, { message }),
  start: async (id) => {
    await post(`/projects/${id}/start`)
  },
  answerCheckin: async (id, checkinId, reply, params) => {
    await post(`/projects/${id}/checkin/${checkinId}`, params === undefined ? { reply } : { reply, params })
  },
  openEvents: (id, onEvent, onReset) => {
    let source: EventSource | null = null
    let closed = false
    let retryMs = 1000

    const connect = () => {
      if (closed) return
      source = new EventSource(`/api/projects/${id}/events`)
      for (const type of EVENT_TYPES) {
        source.addEventListener(type, (raw) => {
          retryMs = 1000
          try {
            onEvent({ type, data: JSON.parse((raw as MessageEvent).data) } as DemoEvent)
          } catch {
            // malformed frame: skip, never break the stream
          }
        })
      }
      source.onerror = () => {
        source?.close()
        if (closed) return
        // backlog replays in full on reconnect, so state rebuilds from zero
        onReset()
        setTimeout(connect, retryMs)
        retryMs = Math.min(retryMs * 2, 15000)
      }
    }
    connect()
    return {
      close() {
        closed = true
        source?.close()
      },
    }
  },
  getPlan: (id) => get(`/projects/${id}/plan`),
  getFunnel: (id) => get(`/projects/${id}/funnel`),
  getLandscape: (id) => get(`/projects/${id}/landscape`),
  getGroups: (id) => get(`/projects/${id}/groups`),
  getEvidence: (id) => get(`/projects/${id}/evidence`),
  getArtefact: (id) => get(`/projects/${id}/artefact`),
  getFindings: (id) => get(`/projects/${id}/findings`),
  getDecisions: (id) => get(`/projects/${id}/decisions`),
  getCoverage: (id) => get(`/projects/${id}/coverage`),
  getSource: (id, sourceId) => get(`/projects/${id}/sources/${sourceId}`),
  getChunkContext: (id, chunkId) => get(`/projects/${id}/chunks/${chunkId}/context`),
}
