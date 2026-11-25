import { useLayoutEffect, useRef } from "react";
import { Outlet, useLocation, useNavigate, useParams } from "react-router";

import { useTask } from "../api/queries";
import { useAuth } from "../auth";
import { AUTH_RETURN_TO_KEY } from "../auth/OidcAuthProvider";
import { scrub } from "../lib/scrub";
import { Button } from "../ui/brand/Button";
import { LifecycleBar, LifecycleBottomBar } from "../ui/brand/LifecycleBar";
import { NavBar, NavHomeLink } from "../ui/brand/Nav";
import { SkipLink, useFocusPaneOnNavigate } from "../ui/brand/SkipLink";
import { cn } from "../ui/brand/cn";
import { TASK_LOCK_ROOT_CLASS, TASK_LOCK_SHELL_CLASS } from "./taskLock";
import { COPY, TASK } from "../lib/vocabulary";
import { ErrorBoundary } from "../ui/feedback/ErrorBoundary";
import { RunStreamProvider } from "../store";
import { ToastProvider } from "../ui/radix/Toast";
import { TooltipProvider } from "../ui/radix/Tooltip";
import { AppFooter } from "./AppFooter";
import { publicLifecycleTabs } from "./lifecycle";
import { PublicViewProvider } from "./publicView";
import { StashAndSplashRedirect } from "../routes/StashAndSplashRedirect";
import { useForgetReportExpandOnLeave } from "./ArtefactOutline";

/**
 * Layout for a public (link-shared) Task opened without signing in.
 * Same URL as the app; only Results and Sources render, behind
 * the backend's public read leg. A Task that is not public (or unknown,
 * or archived) 404s on the tokenless task read and falls through to
 * the stash-and-splash behaviour, so a private link looks
 * like any signed-out link.
 *
 * The run stream never connects (`connect={false}`) and the public-view
 * context disables the chat query and affordances inside the reused
 * views — the page issues only public-surface requests.
 */
export function PublicTaskShell() {
  const { taskId = "" } = useParams();
  // Leaving the task forgets its report's expand state.
  useForgetReportExpandOnLeave(taskId);
  const task = useTask(taskId);
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const oidcConfigured = Boolean(import.meta.env.VITE_OIDC_AUTHORITY);
  const pane = useRef<HTMLDivElement>(null);
  useFocusPaneOnNavigate(pane);

  // Task views lock to the viewport (AppShell does the same): the chrome
  // stays put and only the pane below scrolls.
  useLayoutEffect(() => {
    document.documentElement.classList.add(TASK_LOCK_ROOT_CLASS);
    return () => document.documentElement.classList.remove(TASK_LOCK_ROOT_CLASS);
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
            <div className={cn("flex w-full min-w-0 max-w-full flex-col", TASK_LOCK_SHELL_CLASS)}>
              <SkipLink pane={pane} />
              {/* Its own View Transition layer, held still above the page, so a
                  longlist regroup never draws over it. */}
              <NavBar aria-label="App" className="shrink-0 [view-transition-name:app-nav] [view-transition-class:shell-chrome]">
                <NavHomeLink />
                <Button size="sm" onClick={onSignIn}>
                  Sign in
                </Button>
              </NavBar>
              <NavBar
                aria-label={TASK.one}
                className="shrink-0 bg-ground [view-transition-name:task-nav] [view-transition-class:shell-chrome]"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-lead font-semibold text-navy">
                    {scrub(task.data.name)}
                  </span>
                </div>
                <div className="max-md:hidden">
                  <LifecycleBar hint={COPY.lockedHint} items={publicLifecycleTabs(base)} />
                </div>
              </NavBar>
              <div
                ref={pane}
                tabIndex={-1}
                className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto outline-hidden [scrollbar-gutter:stable] [&>*]:shrink-0"
              >
                <ErrorBoundary key={location.pathname}>
                  <Outlet />
                </ErrorBoundary>
                <AppFooter />
              </div>
              <LifecycleBottomBar hint={COPY.lockedHint} items={publicLifecycleTabs(base)} />
            </div>
          </RunStreamProvider>
        </PublicViewProvider>
      </TooltipProvider>
    </ToastProvider>
  );
}
