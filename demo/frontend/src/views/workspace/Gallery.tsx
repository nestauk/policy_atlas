// The right pane in its browse states: the artifact gallery, and the "new job"
// capability picker it fades into. Same card grammar as the projects homepage.

import { capabilityById, type ArtifactRef, type ArtifactStatus } from './data'
import { CAPABILITIES } from './data'
import { useWorkspace } from './context'
import { Dot } from '../../ui'

const STATUS: Record<ArtifactStatus, { tone: 'progress' | 'done' | 'idle'; label: string }> = {
  draft: { tone: 'idle', label: 'Draft' },
  running: { tone: 'progress', label: 'In progress' },
  complete: { tone: 'done', label: 'Complete' },
}

export default function Gallery() {
  const ws = useWorkspace()
  const picking = ws.view.mode === 'capabilities'

  if (picking) {
    return (
      <div className="thin-scroll h-full overflow-y-auto px-7 py-6">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="font-display text-[20px] font-semibold text-navy">Start a new job</h2>
            <p className="mt-0.5 text-[12.5px] text-grey">
              Pick a capability. A new chat opens so you can brief the orchestrator.
            </p>
          </div>
          <button className="btn btn--sec" onClick={ws.openGallery}>Cancel</button>
        </div>
        <CapabilityGrid />
      </div>
    )
  }

  return (
    <div className="thin-scroll flex h-full flex-col overflow-y-auto px-7 py-6">
      <div className="mb-5 flex justify-end">
        <button className="btn" onClick={ws.openCapabilities}>+ New job</button>
      </div>
      <ArtifactGrid />
    </div>
  )
}

function ArtifactGrid() {
  const ws = useWorkspace()
  if (ws.artifacts.length === 0) {
    return <div className="flex-1" aria-hidden />
  }
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {ws.artifacts.map((a, i) => (
        <ArtifactCard key={a.id} artifact={a} delayMs={Math.min(i, 8) * 60} />
      ))}
    </div>
  )
}

function ArtifactCard({ artifact: a, delayMs }: { artifact: ArtifactRef; delayMs: number }) {
  const ws = useWorkspace()
  const cap = capabilityById(a.capability)
  const st = STATUS[a.status]
  return (
    <div
      role="button"
      tabIndex={0}
      className="anim-rise group flex min-h-[150px] cursor-pointer flex-col justify-between bg-white p-5 text-left shadow-card ring-1 ring-line transition-shadow hover:shadow-panel focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue"
      style={{ animationDelay: `${delayMs}ms` }}
      onClick={() => ws.openArtifact(a.id)}
      onKeyDown={(e) => e.key === 'Enter' && ws.openArtifact(a.id)}
    >
      <div>
        <div className="text-[10.5px] font-extrabold uppercase tracking-[.06em] text-blue">{cap.title}</div>
        <div className="mt-1.5 text-[15px] font-bold leading-snug text-navy">{a.title}</div>
        <div className="mt-1.5 line-clamp-2 text-[12.5px] text-grey">{a.subtitle}</div>
      </div>
      <div className="mt-4 flex items-center justify-between">
        <span className="flex items-center gap-2 text-[12.5px] font-medium text-navy">
          <Dot tone={st.tone} /> {st.label}
        </span>
        <span className="text-[12px] text-grey">{a.updatedAt}</span>
      </div>
    </div>
  )
}

function CapabilityGrid() {
  const ws = useWorkspace()
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {CAPABILITIES.map((c, i) => (
        <button
          key={c.id}
          className="anim-rise flex min-h-[130px] flex-col justify-between border border-line-2 bg-white p-5 text-left shadow-card transition-shadow hover:shadow-panel hover:ring-1 hover:ring-blue focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue"
          style={{ animationDelay: `${Math.min(i, 8) * 50}ms` }}
          onClick={() => ws.startJob(c.id)}
        >
          <div className="text-[15px] font-bold leading-snug text-navy">{c.title}</div>
          <div className="mt-1.5 text-[12.5px] leading-snug text-grey">{c.blurb}</div>
        </button>
      ))}
    </div>
  )
}
