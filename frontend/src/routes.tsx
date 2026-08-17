import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router";

import { AppShell } from "./views/AppShell";
import { ArtefactView } from "./views/ArtefactView";
import { DecisionsView } from "./views/DecisionsView";
import { FindingsView } from "./views/FindingsView";
import { LandingView } from "./views/LandingView";
import { LifecycleRoute, RedirectToPath } from "./views/LifecycleRoute";
import { NewTaskView } from "./views/NewTaskView";
import { ShareView } from "./views/ShareView";
import { SourcesLayout } from "./views/SourcesLayout";
import { SourcesView } from "./views/SourcesView";
import { ThemesView } from "./views/ThemesView";
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
      { path: "/new", element: <NewTaskView /> },

      // The task lifecycle: Plan · Results · Sources · Share · History.
      // Every stage past Plan is gated on run state, so a locked stage is
      // unreachable by URL as well as by click.
      { path: "/projects/:projectId", element: <WorkspaceView /> },
      {
        path: "/projects/:projectId/results",
        element: (
          <LifecycleRoute tab="results">
            <ArtefactView />
          </LifecycleRoute>
        ),
      },
      {
        path: "/projects/:projectId/sources",
        element: (
          <LifecycleRoute tab="sources">
            <SourcesLayout />
          </LifecycleRoute>
        ),
        children: [
          { index: true, element: <ThemesView /> },
          {
            path: "landscape",
            element: (
              <Suspense fallback={<LandscapeFallback />}>
                <LandscapeView />
              </Suspense>
            ),
          },
          { path: "all", element: <SourcesView /> },
          { path: "findings", element: <FindingsView /> },
        ],
      },
      {
        path: "/projects/:projectId/share",
        element: (
          <LifecycleRoute tab="share">
            <ShareView />
          </LifecycleRoute>
        ),
      },
      {
        path: "/projects/:projectId/history",
        element: (
          <LifecycleRoute tab="history">
            <DecisionsView />
          </LifecycleRoute>
        ),
      },

      // Retired paths. Every URL that was bookmarkable before the reshape
      // still resolves — a reorganisation is not a reason to break someone's
      // saved link.
      { path: "/projects/:projectId/evidence-base", element: <RedirectToPath suffix="/results" /> },
      { path: "/projects/:projectId/findings", element: <RedirectToPath suffix="/sources/findings" /> },
      { path: "/projects/:projectId/landscape", element: <RedirectToPath suffix="/sources/landscape" /> },
      { path: "/projects/:projectId/decisions", element: <RedirectToPath suffix="/history" /> },

      // Catch-all: an unknown URL still gets the app chrome and an honest
      // "nothing here" view rather than a router error page.
      { path: "*", element: <NotFoundView /> },
    ],
  },
]);
