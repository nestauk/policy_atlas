// App chrome: two-tone masthead, breadcrumb, project tab nav. The Findings tab
// only exists when extraction actually produced findings — no empty surfaces.

import { NavLink, useParams } from 'react-router-dom'
import { type ReactNode } from 'react'
import { MOCK } from './api'
import { useProject } from './store'

export function Masthead({ crumb, tabs }: { crumb?: ReactNode; tabs?: ReactNode }) {
  return (
    <header className="flex h-[58px] items-center justify-between border-b hairline bg-white px-6">
      <div className="flex min-w-0 items-center gap-3">
        <NavLink to="/" className="whitespace-nowrap font-display text-[18px] font-extrabold tracking-tight text-navy">
          Policy <b className="text-blue">Atlas</b>
        </NavLink>
        {MOCK && <span className="chip chip--soft">rehearsal</span>}
        {crumb && (
          <span className="flex min-w-0 items-center gap-2 text-[13px] text-grey">
            <span className="text-line-2">/</span>
            <span className="truncate font-semibold text-navy">{crumb}</span>
          </span>
        )}
      </div>
      {tabs}
    </header>
  )
}

export function ProjectTabs() {
  const { id } = useParams<{ id: string }>()
  const { state } = useProject()
  const hasFindings = (state.funnel?.findings ?? 0) > 0
  const hasArtefact =
    state.phase === 'complete' || (state.funnel?.cited ?? 0) > 0 || state.liveSections.length > 0

  const tab = (to: string, label: string, end = false) => (
    <NavLink
      key={label}
      to={to}
      end={end}
      className={({ isActive }) =>
        `border-b-2 pb-0.5 text-[13px] transition-colors ${
          isActive ? 'border-blue font-extrabold text-navy' : 'border-transparent font-semibold text-grey hover:text-navy'
        }`
      }
    >
      {label}
    </NavLink>
  )

  return (
    <nav className="flex items-center gap-5" aria-label="Project">
      {tab(`/project/${id}`, 'Workspace', true)}
      {hasArtefact && tab(`/project/${id}/evidence-base`, 'Evidence base')}
      {hasFindings && tab(`/project/${id}/findings`, 'Findings')}
      {tab(`/project/${id}/sources`, 'Sources')}
      {tab(`/project/${id}/decisions`, 'Decision log')}
    </nav>
  )
}

export function ProjectCrumb() {
  const { state } = useProject()
  return state.plan?.title || state.plan?.question || ''
}
