import { Outlet, Route, Routes, useParams } from 'react-router-dom'
import { ProjectProvider } from './store'
import { SourcePanelProvider } from './sourcePanel'
import { WorkspaceProvider } from './views/workspace/context'
import { Masthead, ProjectCrumb, ProjectTabs } from './shell'
import Landing from './views/Landing'
import Workspace from './views/Workspace'
import Sources from './views/Sources'
import Chats from './views/Chats'

function ProjectShell() {
  const { id } = useParams<{ id: string }>()
  return (
    <ProjectProvider projectId={id!}>
      <SourcePanelProvider projectId={id!}>
        <WorkspaceProvider>
          <Masthead crumb={<ProjectCrumb />} tabs={<ProjectTabs />} />
          <Outlet />
        </WorkspaceProvider>
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
        <Route path="chats" element={<Chats />} />
        <Route path="sources" element={<Sources />} />
      </Route>
    </Routes>
  )
}
