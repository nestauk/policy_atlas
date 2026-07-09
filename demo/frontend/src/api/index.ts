import { liveApi } from './client'
import { mockApi } from './mock'
import type { DemoApi } from './types'

export const MOCK = import.meta.env.VITE_MOCK === '1'
export const api: DemoApi = MOCK ? mockApi : liveApi
export * from './types'
