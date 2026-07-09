// The demo API contract — mirrors demo/API.md exactly. The mock implements the
// same interface as the live client, so every UI behaviour is rehearsable.

export type ProjectStatus = 'new' | 'planning' | 'running' | 'complete' | 'failed'

export interface Project {
  project_id: string
  name: string
  question: string | null
  status: ProjectStatus
  created_at: string
  source_count: number
}

export interface PlanStep {
  label: string
  stage: string
}

export interface Plan {
  question: string | null
  focus: string[]
  search_depth: 'quick' | 'deep'
  evidence_sources: 'academic_only' | 'grey_lit_only' | 'both'
  check_in: 'minimal' | 'moderate' | 'frequent'
  title?: string
  steps: PlanStep[]
  ready: boolean
}

export interface Funnel {
  found: number | null
  relevant: number | null
  screened_out: number | null
  quality_checked: number | null
  read_in_full: number | null
  selected: number | null
  findings: number | null
  cited: number | null
}

export interface Theme {
  name: string
  size: number
  description: string
}

export interface Landscape {
  evidence_types: Record<string, number>
  years: Record<string, number>
  themes: Theme[]
  publication_countries?: Record<string, number>
}

export interface FacetGroup {
  label: string
  description: string
  size: number
}

export interface Groups {
  facets: { facet: string; groups: FacetGroup[]; ungrouped: number }[]
}

export type EvidenceStatus =
  | 'found' | 'screened_out' | 'relevant' | 'not_selected' | 'selected'
  | 'read_in_full' | 'findings_extracted' | 'cited' | 'unavailable'

export interface EvidenceRow {
  source_id: string
  title: string
  year: number | null
  venue: string
  origin: string
  status: EvidenceStatus
  status_reason: string | null
  evidence_type: string | null
  appraisal_tier: string | null
  appraisal_label: string | null
  cited: boolean
  url: string | null
  screen_confidence: number | null
  screen_basis: string | null
  screen_stage: number | null
}

export type ClaimType = 'citation' | 'gap' | 'reasoning' | 'pattern' | 'theme'

export interface Citation {
  n: number
  source_title: string
  quote: string
  verified: boolean
  grounding_tier: string | null
  appraisal_label: string | null
  chunk_id: string
}

export interface Claim {
  claim_id: string
  claim_type: ClaimType
  text: string
  span: { start: number; end: number | null } | null
  citations: Citation[]
}

export interface Block {
  block_id: string
  prose: string
  claims: Claim[]
}

export interface Artefact {
  title: string
  question: string
  coverage_snapshot: {
    source_count: number
    study_types: Record<string, number>
    year_range: { min: number; max: number } | null
    included: number
    screened_out: number
  }
  sections: { title: string; blocks: Block[] }[]
  references: { n: number; title: string; year: number | null; venue: string; url: string | null }[]
}

export interface Finding {
  finding_id: string
  source_id: string
  intervention: string
  outcome: string
  direction: 'positive' | 'negative' | 'no_effect' | 'mixed' | 'unclear'
  population: string | null
  comparator: string | null
  study_design: string | null
  estimate_level: string | null
  causality: string | null
  is_primary: boolean | null
  statistics: Record<string, unknown>
  stratum_qualifiers: { type: string; value: string }[]
  quote: string | null
  quote_verified: boolean
  source_title: string
  groups: Record<string, string>
}

export interface DecisionEntry {
  at: string
  kind: string
  text: string
  detail: Record<string, string | number>
}

export interface Coverage {
  backends: string[]
  stop_condition: string
  summary?: string
  adequacy: 'adequate' | 'inadequate'
}

export interface SourceDossier extends EvidenceRow {
  abstract: string | null
  doi: string | null
  language: string | null
  publisher_org: string | null
  record_type: string | null
  cited_by_count: number | null
  fwci: number | null
  tags: { tag: string; tag_type: string; asserted_by: string }[]
  cited_claims: { claim: string; quote: string; verified: boolean; section: string }[]
}

export interface ChunkContext {
  previous: string | null
  content: string
  next: string | null
  source_title: string
  year: number | null
  venue: string
}

// --- SSE events ---

export type DemoEvent =
  | { type: 'plan.updated'; data: { plan: Plan } }
  | { type: 'analysis.started'; data: Record<string, never> }
  | { type: 'stage.started'; data: { stage: string; stage_label: string; stage_blurb: string } }
  | { type: 'stage.progress'; data: ProgressData }
  | { type: 'stage.completed'; data: { stage: string; stage_label: string; summary: Record<string, number> } }
  | { type: 'stage.failed'; data: { stage: string; stage_label: string; reason: string } }
  | { type: 'narration'; data: { text: string } }
  | { type: 'user.message'; data: { text: string } }
  | { type: 'checkin'; data: { checkin_id: string; text: string; options: string[] } }
  | { type: 'checkin.resolved'; data: { checkin_id: string; reply: string } }
  | { type: 'analysis.completed'; data: Record<string, never> }
  | { type: 'analysis.failed'; data: { stage: string | null; message: string } }

export interface ProgressData {
  stage: string | null
  kind: 'search_query' | 'results' | 'round' | 'fetch' | 'tick'
  backend?: string
  query?: string
  count?: number
  note?: string
  [k: string]: unknown
}

export const EVENT_TYPES: DemoEvent['type'][] = [
  'plan.updated', 'analysis.started', 'stage.started', 'stage.progress',
  'stage.completed', 'stage.failed', 'narration', 'user.message', 'checkin',
  'checkin.resolved', 'analysis.completed', 'analysis.failed',
]

export interface DemoApi {
  listProjects(): Promise<Project[]>
  createProject(name: string): Promise<{ project_id: string }>
  chat(projectId: string, message: string): Promise<{ reply: string; plan: Plan }>
  start(projectId: string): Promise<void>
  answerCheckin(projectId: string, checkinId: string, reply: string): Promise<void>
  openEvents(projectId: string, onEvent: (e: DemoEvent) => void, onReset: () => void): { close(): void }
  getPlan(projectId: string): Promise<Plan>
  getFunnel(projectId: string): Promise<Funnel>
  getLandscape(projectId: string): Promise<Landscape | null>
  getGroups(projectId: string): Promise<Groups | null>
  getEvidence(projectId: string): Promise<EvidenceRow[]>
  getArtefact(projectId: string): Promise<Artefact | null>
  getFindings(projectId: string): Promise<Finding[]>
  getDecisions(projectId: string): Promise<DecisionEntry[]>
  getCoverage(projectId: string): Promise<Coverage | null>
  getSource(projectId: string, sourceId: string): Promise<SourceDossier | null>
  getChunkContext(projectId: string, chunkId: string): Promise<ChunkContext | null>
}
