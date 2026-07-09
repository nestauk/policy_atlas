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
            <button
              key={p.project_id}
              className="anim-rise flex min-h-[150px] flex-col justify-between bg-white p-5 text-left shadow-card ring-1 ring-line transition-shadow hover:shadow-panel focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue"
              style={{ animationDelay: `${Math.min(i, 8) * 60}ms` }}
              onClick={() => navigate(`/project/${p.project_id}`)}
            >
              <div>
                <div className="text-[15px] font-bold leading-snug text-navy">{p.name}</div>
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
            </button>
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
