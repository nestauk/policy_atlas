import { Outlet, Route, Routes, useParams } from 'react-router-dom'
import { ProjectProvider } from './store'
import { SourcePanelProvider } from './sourcePanel'
import { Masthead, ProjectCrumb, ProjectTabs } from './shell'
import Landing from './views/Landing'
import Workspace from './views/Workspace'
import EvidenceBase from './views/EvidenceBase'
import Findings from './views/Findings'
import Sources from './views/Sources'
import DecisionLog from './views/DecisionLog'

function ProjectShell() {
  const { id } = useParams<{ id: string }>()
  return (
    <ProjectProvider projectId={id!}>
      <SourcePanelProvider projectId={id!}>
        <Masthead crumb={<ProjectCrumb />} tabs={<ProjectTabs />} />
        <Outlet />
      </SourcePanelProvider>
    </ProjectProvider>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/project/:id" element={<ProjectShell />}>
        <Route index element={<Workspace />} />
        <Route path="evidence-base" element={<EvidenceBase />} />
        <Route path="findings" element={<Findings />} />
        <Route path="sources" element={<Sources />} />
        <Route path="decisions" element={<DecisionLog />} />
      </Route>
    </Routes>
  )
}
