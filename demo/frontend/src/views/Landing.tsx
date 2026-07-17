// Projects landing — calm and functional, no marketing hero (wireframe 00).

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Project } from '../api'
import { Masthead } from '../shell'
import { Dot } from '../ui'

const STATUS: Record<Project['status'], { tone: 'progress' | 'done' | 'paused' | 'idle'; label: string }> = {
  new: { tone: 'idle', label: 'New' },
  planning: { tone: 'idle', label: 'Planning' },
  running: { tone: 'progress', label: 'Analysing' },
  paused: { tone: 'paused', label: 'Paused — waiting on your input' },
  complete: { tone: 'done', label: 'Complete' },
  failed: { tone: 'paused', label: 'Stopped' },
}

export default function Landing() {
  const [projects, setProjects] = useState<Project[] | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    api.listProjects().then(setProjects).catch(() => setProjects([]))
  }, [])

  const create = async () => {
    const { project_id } = await api.createProject('Untitled project')
    navigate(`/project/${project_id}`)
  }

  const patchLocal = (id: string, patch: Partial<Project>) =>
    setProjects((ps) => (ps ?? []).map((p) => (p.project_id === id ? { ...p, ...patch } : p)))

  const rename = async (id: string, name: string, question: string) => {
    patchLocal(id, { name, question })
    await api.updateProject(id, { name, question }).catch(() => {})
  }

  const remove = async (id: string) => {
    setProjects((ps) => (ps ?? []).filter((p) => p.project_id !== id))
    await api.deleteProject(id).catch(() => {})
  }

  return (
    <div className="min-h-screen">
      <Masthead />
      <main className="mx-auto max-w-[1180px] px-8 py-10">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-display text-[28px] font-extrabold text-navy">Projects</h1>
          <button className="btn" onClick={create}>+ New project</button>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(projects ?? []).map((p, i) => (
            <ProjectCard
              key={p.project_id}
              project={p}
              delayMs={Math.min(i, 8) * 60}
              onOpen={() => navigate(`/project/${p.project_id}`)}
              onRename={(name, question) => void rename(p.project_id, name, question)}
              onDelete={() => void remove(p.project_id)}
            />
          ))}

          <button
            className="flex min-h-[150px] items-center justify-center border border-dashed border-line-2 text-[13px] font-semibold text-grey transition-colors hover:border-navy-40 hover:text-navy"
            onClick={create}
          >
            + New project
          </button>
        </div>

        {projects === null && <p className="mt-8 text-[13px] text-grey">Loading projects…</p>}
      </main>
    </div>
  )
}

function ProjectCard({
  project: p,
  delayMs,
  onOpen,
  onRename,
  onDelete,
}: {
  project: Project
  delayMs: number
  onOpen: () => void
  onRename: (name: string, question: string) => void
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [name, setName] = useState(p.name)
  const [question, setQuestion] = useState(p.question ?? '')

  const save = () => {
    setEditing(false)
    if (name.trim()) onRename(name.trim(), question.trim())
  }

  if (editing) {
    return (
      <div
        className="anim-rise flex min-h-[150px] flex-col gap-2 bg-white p-5 shadow-panel ring-1 ring-blue"
        style={{ animationDelay: `${delayMs}ms` }}
      >
        <input
          className="h-8 border hairline px-2 text-[14px] font-bold text-navy outline-none focus:border-blue"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Project name"
          autoFocus
          onKeyDown={(e) => e.key === 'Enter' && save()}
        />
        <textarea
          className="min-h-[48px] flex-1 border hairline px-2 py-1.5 text-[12.5px] leading-snug text-navy outline-none focus:border-blue"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Description — the question this project answers"
        />
        <div className="flex gap-2">
          <button className="btn !py-1 !text-[12px]" disabled={!name.trim()} onClick={save}>
            Save
          </button>
          <button
            className="btn btn--ghost !py-1 !text-[12px]"
            onClick={() => { setEditing(false); setName(p.name); setQuestion(p.question ?? '') }}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div
      role="button"
      tabIndex={0}
      className="anim-rise group relative flex min-h-[150px] cursor-pointer flex-col justify-between bg-white p-5 text-left shadow-card ring-1 ring-line transition-shadow hover:shadow-panel focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue"
      style={{ animationDelay: `${delayMs}ms` }}
      onClick={onOpen}
      onKeyDown={(e) => e.key === 'Enter' && onOpen()}
      onMouseLeave={() => setConfirming(false)}
    >
      <div className="absolute right-3 top-3 flex gap-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
        <button
          className="btn btn--ghost !px-2 !py-0.5 !text-[11.5px]"
          onClick={(e) => { e.stopPropagation(); setEditing(true) }}
        >
          Rename
        </button>
        <button
          className={`btn !px-2 !py-0.5 !text-[11.5px] ${confirming ? '' : 'btn--ghost'}`}
          onClick={(e) => {
            e.stopPropagation()
            if (confirming) onDelete()
            else setConfirming(true)
          }}
        >
          {confirming ? 'Confirm delete' : 'Delete'}
        </button>
      </div>
      <div>
        <div className="pr-32 text-[15px] font-bold leading-snug text-navy">{p.name}</div>
        <div className="mt-1.5 line-clamp-2 text-[12.5px] text-grey">
          {p.question || <span className="italic">No question yet</span>}
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between">
        <span className="flex items-center gap-2 text-[12.5px] font-medium text-navy">
          <Dot tone={STATUS[p.status].tone} /> {STATUS[p.status].label}
        </span>
        {p.source_count > 0 && (
          <span className="text-[12px] text-grey">{p.source_count} sources</span>
        )}
      </div>
    </div>
  )
}
