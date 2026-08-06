import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router";

import { AppShell } from "./views/AppShell";
import { ArtefactView } from "./views/ArtefactView";
import { DecisionsView } from "./views/DecisionsView";
import { FindingsView } from "./views/FindingsView";
import { LandingView } from "./views/LandingView";
import { SourcesView } from "./views/SourcesView";
import { WorkspaceView } from "./views/WorkspaceView";
import { NotFoundView } from "./ui/feedback/NotFoundView";

// Lazy: `recharts` is a substantial dependency only the landscape route
// needs — keeping it out of the main chunk means every other route (and
// the initial page load) doesn't pay for it.
const LandscapeView = lazy(() =>
  import("./views/LandscapeView").then((module) => ({ default: module.LandscapeView })),
);

function LandscapeFallback() {
  return (
    <main aria-busy="true" aria-label="Loading landscape" className="mx-auto max-w-5xl px-6 py-10">
      <div className="h-64 animate-pulse border border-line bg-paper-2" />
    </main>
  );
}

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
      {
        path: "/projects/:projectId/landscape",
        element: (
          <Suspense fallback={<LandscapeFallback />}>
            <LandscapeView />
          </Suspense>
        ),
      },
      { path: "/projects/:projectId/decisions", element: <DecisionsView /> },
      // Catch-all: an unknown URL still gets the app chrome and an honest
      // "nothing here" view rather than a router error page.
      { path: "*", element: <NotFoundView /> },
    ],
  },
]);
