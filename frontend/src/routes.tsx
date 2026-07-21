import { createBrowserRouter } from "react-router";

import { AppShell } from "./views/AppShell";
import { ArtefactView } from "./views/ArtefactView";
import { DecisionsView } from "./views/DecisionsView";
import { FindingsView } from "./views/FindingsView";
import { LandingView } from "./views/LandingView";
import { LandscapeView } from "./views/LandscapeView";
import { SourcesView } from "./views/SourcesView";
import { WorkspaceView } from "./views/WorkspaceView";

/** UI state that names a thing is URL-addressable: views are routes, the
 * dossier and filters are search params — deep-linkable and refresh-safe. */
export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <LandingView /> },
      { path: "/projects/:projectId", element: <WorkspaceView /> },
      { path: "/projects/:projectId/evidence-base", element: <ArtefactView /> },
      { path: "/projects/:projectId/findings", element: <FindingsView /> },
      { path: "/projects/:projectId/sources", element: <SourcesView /> },
      { path: "/projects/:projectId/landscape", element: <LandscapeView /> },
      { path: "/projects/:projectId/decisions", element: <DecisionsView /> },
    ],
  },
]);
