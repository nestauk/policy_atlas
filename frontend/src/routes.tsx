import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router";

import { AppShell } from "./views/AppShell";
import { ArtefactView } from "./views/ArtefactView";
import { FindingsView } from "./views/FindingsView";
import { HistoryView } from "./views/HistoryView";
import { LifecycleRoute, RedirectToPath } from "./views/LifecycleRoute";
import { NewTaskView } from "./views/NewTaskView";
import { PortfolioDetailView, PortfoliosView } from "./views/PortfoliosView";
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
 *  view (task 037): the same `/projects/…` URLs render Results and Sources
 *  for a public Task; anything else under the task redirects to Results,
 *  and a non-public Task falls through to stash-and-splash inside
 *  `PublicTaskShell`. */
export const publicRouter = createBrowserRouter([
  { path: "/", element: <SplashView /> },
  { path: "/privacy", element: <PrivacyView /> },
  { path: "/terms", element: <TermsView /> },
  {
    path: "/projects/:projectId",
    element: <PublicTaskShell />,
    children: [
      { index: true, element: <RedirectToPath suffix="/results" /> },
      { path: "results", element: <ArtefactView /> },
      { path: "sources", element: <SourcesLayout />, children: sourcesChildren },
      // `preserveOriginal` (task 037 review fix): this can fire on a
      // read that was public when it resolved but is unshared before a
      // stashed refetch settles — carry the original deep link so
      // `StashAndSplashRedirect` never stashes the rewritten `/results`
      // path instead of it.
      { path: "*", element: <RedirectToPath suffix="/results" preserveOriginal /> },
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
          { path: "/portfolios", element: <PortfoliosView /> },
          { path: "/portfolios/:portfolioId", element: <PortfolioDetailView /> },
          { path: "/privacy", element: <PrivacyView /> },
          { path: "/terms", element: <TermsView /> },

          {
            path: "/projects/:projectId",
            element: (
              // Plan is open at every run state; the wrapper exists for the
              // public-leg gate (task 037) — a signed-in outsider on a
              // public Task lands on Results, never the Plan.
              <LifecycleRoute tab="plan">
                <WorkspaceView />
              </LifecycleRoute>
            ),
          },
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
            children: sourcesChildren,
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
                <HistoryView />
              </LifecycleRoute>
            ),
          },

          { path: "/projects/:projectId/evidence-base", element: <RedirectToPath suffix="/results" /> },
          {
            path: "/projects/:projectId/findings",
            element: <RedirectToPath suffix="/sources/findings" />,
          },
          {
            path: "/projects/:projectId/landscape",
            element: <RedirectToPath suffix="/sources/landscape" />,
          },
          { path: "/projects/:projectId/decisions", element: <RedirectToPath suffix="/history" /> },

          { path: "*", element: <NotFoundView /> },
        ],
      },
    ],
  },
]);
