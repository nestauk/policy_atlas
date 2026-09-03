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

/** Logged-out marketing + legal routes (no AppShell). */
export const publicRouter = createBrowserRouter([
  { path: "/", element: <SplashView /> },
  { path: "/privacy", element: <PrivacyView /> },
  { path: "/terms", element: <TermsView /> },
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
