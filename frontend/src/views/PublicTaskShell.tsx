import { useLayoutEffect } from "react";
import { Outlet, useLocation, useNavigate, useParams } from "react-router";

import { useTask } from "../api/queries";
import { useAuth } from "../auth";
import { AUTH_RETURN_TO_KEY } from "../auth/OidcAuthProvider";
import { scrub } from "../lib/scrub";
import { Button } from "../ui/brand/Button";
import { LifecycleBar } from "../ui/brand/LifecycleBar";
import { NavBar, NavHomeLink } from "../ui/brand/Nav";
import { COPY, TASK } from "../lib/vocabulary";
import { ErrorBoundary } from "../ui/feedback/ErrorBoundary";
import { RunStreamProvider } from "../store";
import { ToastProvider } from "../ui/radix/Toast";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { AppFooter } from "./AppFooter";
import { publicLifecycleTabs } from "./lifecycle";
import { PublicViewProvider } from "./publicView";
import { StashAndSplashRedirect } from "../routes/StashAndSplashRedirect";

/**
 * Layout for a public (link-shared) Task opened without signing in —
 * task 037. Same URL as the app; only Results and Sources render, behind
 * the backend's public read leg. A Task that is not public (or unknown,
 * or archived) 404s on the tokenless task read and falls through to
 * the existing stash-and-splash behaviour, so a private link looks
 * exactly like it did before this slice.
 *
 * The run stream never connects (`connect={false}`) and the public-view
 * context disables the chat query and affordances inside the reused
 * views — the page issues only public-surface requests.
 */
export function PublicTaskShell() {
  const { taskId = "" } = useParams();
  const task = useTask(taskId);
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const oidcConfigured = Boolean(import.meta.env.VITE_OIDC_AUTHORITY);

  // Task views lock to the viewport (AppShell does the same): the chrome
  // stays put and only the pane below scrolls.
  useLayoutEffect(() => {
    document.documentElement.classList.add("overflow-hidden");
    return () => document.documentElement.classList.remove("overflow-hidden");
  }, []);

  if (task.isPending) {
    return (
      <p role="status" className="text-meta text-grey">
        Loading…
      </p>
    );
  }
  if (task.data === undefined) {
    return <StashAndSplashRedirect />;
  }

  const base = `/tasks/${taskId}`;

  const onSignIn = () => {
    const returnTo = `${location.pathname}${location.search}${location.hash}`;
    sessionStorage.setItem(AUTH_RETURN_TO_KEY, returnTo);
    if (!oidcConfigured) {
      // Dev-token sign-in lives on the splash page.
      void navigate("/");
      return;
    }
    void auth.signIn();
  };

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <PublicViewProvider value={true}>
          <RunStreamProvider taskId={taskId} connect={false}>
            <div className="flex h-svh w-full min-w-0 max-w-full flex-col overflow-hidden">
              <NavBar aria-label="App" className="shrink-0">
                <NavHomeLink />
                <Button size="sm" onClick={onSignIn}>
                  Sign in
                </Button>
              </NavBar>
              <NavBar aria-label={TASK.one} className="shrink-0 bg-ground">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-lead font-semibold text-navy">
                    {scrub(task.data.name)}
                  </span>
                </div>
                <LifecycleBar hint={COPY.lockedHint} items={publicLifecycleTabs(base)} />
              </NavBar>
              <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto [scrollbar-gutter:stable] [&>*]:shrink-0">
                <ErrorBoundary key={location.pathname}>
                  <Outlet />
                </ErrorBoundary>
                <AppFooter />
              </div>
            </div>
          </RunStreamProvider>
        </PublicViewProvider>
      </TooltipProvider>
    </ToastProvider>
  );
}
