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
import { PublicTaskShell } from "./views/PublicTaskShell";
import { SplashView } from "./views/splash/SplashView";
import { NotFoundView } from "./ui/feedback/NotFoundView";
import { RequireAuth } from "./routes/RequireAuth";
import { StashAndSplashRedirect } from "./routes/StashAndSplashRedirect";

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

/** The Sources sub-tree, shared verbatim by the authenticated app and the
 *  public task view (task 037) — same paths, same components. */
const sourcesChildren = [
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
];

/** Logged-out marketing + legal routes (no AppShell), plus the public task
 *  view (task 037): the same `/tasks/…` URLs render Result and Sources
 *  for a public Task; anything else under the task redirects to Result,
 *  and a non-public Task falls through to stash-and-splash inside
 *  `PublicTaskShell`. */
export const publicRouter = createBrowserRouter([
  { path: "/", element: <SplashView /> },
  { path: "/privacy", element: <PrivacyView /> },
  { path: "/terms", element: <TermsView /> },
  {
    path: "/tasks/:taskId",
    element: <PublicTaskShell />,
    children: [
      { index: true, element: <RedirectToPath suffix="/result" /> },
      { path: "result", element: <ArtefactView /> },
      { path: "sources", element: <SourcesLayout />, children: sourcesChildren },
      // `preserveOriginal` (task 037 review fix): this can fire on a
      // read that was public when it resolved but is unshared before a
      // stashed refetch settles — carry the original deep link so
      // `StashAndSplashRedirect` never stashes the rewritten `/result`
      // path instead of it.
      { path: "*", element: <RedirectToPath suffix="/result" preserveOriginal /> },
    ],
  },
  { path: "*", element: <StashAndSplashRedirect /> },
]);

/** Authenticated app routes behind RequireAuth + AppShell. */
export const authenticatedRouter = createBrowserRouter([
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "/", element: <TasksListView /> },
          { path: "/new", element: <NewTaskView /> },
          { path: "/projects", element: <ProjectsView /> },
          { path: "/projects/:projectId", element: <ProjectDetailView /> },
          { path: "/privacy", element: <PrivacyView /> },
          { path: "/terms", element: <TermsView /> },

          {
            path: "/tasks/:taskId",
            element: (
              // Agent is open at every run state; the wrapper exists for the
              // public-leg gate (task 037) — a signed-in outsider on a
              // public Task lands on Result, never the Agent tab.
              <LifecycleRoute tab="agent">
                <WorkspaceView />
              </LifecycleRoute>
            ),
          },
          {
            path: "/tasks/:taskId/result",
            element: (
              <LifecycleRoute tab="result">
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
            children: sourcesChildren,
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

          { path: "*", element: <NotFoundView /> },
        ],
      },
    ],
  },
]);
