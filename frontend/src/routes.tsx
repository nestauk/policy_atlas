import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router";

import { AppShell } from "./views/AppShell";
import { ArtefactView } from "./views/ArtefactView";
import { FindingsView } from "./views/FindingsView";
import { HistoryView } from "./views/HistoryView";
import { LifecycleRoute, RedirectToPath } from "./views/LifecycleRoute";
import { NewTaskView } from "./views/NewTaskView";
import { ProjectDetailView, ProjectsView } from "./views/ProjectsView";
import { ShareView } from "./views/ShareView";
import { SourcesLayout } from "./views/SourcesLayout";
import { SourcesView } from "./views/SourcesView";
import { TasksListView } from "./views/TasksListView";
import { ThemesView } from "./views/ThemesView";
import { WorkspaceView } from "./views/WorkspaceView";
import { PrivacyView } from "./views/legal/PrivacyView";
import { TermsView } from "./views/legal/TermsView";
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
      { path: "/", element: <TasksListView /> },
      { path: "/new", element: <NewTaskView /> },
      { path: "/projects", element: <ProjectsView /> },
      { path: "/projects/:projectId", element: <ProjectDetailView /> },
      { path: "/privacy", element: <PrivacyView /> },
      { path: "/terms", element: <TermsView /> },

      // The task lifecycle: Plan · Results · Sources · Share · History.
      // Every stage past Plan is gated on run state, so a locked stage is
      // unreachable by URL as well as by click.
      { path: "/tasks/:taskId", element: <WorkspaceView /> },
      {
        path: "/tasks/:taskId/results",
        element: (
          <LifecycleRoute tab="results">
            <ArtefactView />
          </LifecycleRoute>
        ),
      },
      {
        path: "/tasks/:taskId/sources",
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
        path: "/tasks/:taskId/share",
        element: (
          <LifecycleRoute tab="share">
            <ShareView />
          </LifecycleRoute>
        ),
      },
      {
        path: "/tasks/:taskId/history",
        element: (
          <LifecycleRoute tab="history">
            <HistoryView />
          </LifecycleRoute>
        ),
      },

      // Retired paths. Every URL that was bookmarkable before the reshape
      // still resolves — a reorganisation is not a reason to break someone's
      // saved link.
      { path: "/tasks/:taskId/evidence-search", element: <RedirectToPath suffix="/results" /> },
      { path: "/tasks/:taskId/findings", element: <RedirectToPath suffix="/sources/findings" /> },
      { path: "/tasks/:taskId/landscape", element: <RedirectToPath suffix="/sources/landscape" /> },
      { path: "/tasks/:taskId/decisions", element: <RedirectToPath suffix="/history" /> },

      // Catch-all: an unknown URL still gets the app chrome and an honest
      // "nothing here" view rather than a router error page.
      { path: "*", element: <NotFoundView /> },
    ],
  },
]);
