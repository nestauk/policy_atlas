import { Outlet, useLocation, useParams } from "react-router";

import { useCheckIns, useProject } from "../api/queries";
import { useAuth } from "../auth";
import { TitleMarkerProvider } from "../lib/title";
import { scrub } from "../lib/scrub";
import { StatusDot } from "../ui/brand/Card";
import { NavBar, NavItem, NavLogo } from "../ui/brand/Nav";
import { ErrorBoundary } from "../ui/feedback/ErrorBoundary";
import { ToastProvider } from "../ui/radix/Toast";
import { TooltipProvider } from "../ui/radix/Tooltip";

/** App chrome: brand group left, project-scoped nav right (growing underline). */
export function AppShell() {
  const { projectId } = useParams();
  const location = useLocation();
  const auth = useAuth();
  const project = useProject(projectId ?? "");
  const base = projectId === undefined ? null : `/projects/${projectId}`;
  const inWorkspace = base !== null && location.pathname === base;

  // Pending check-in visibility outside the workspace (contract strand 14):
  // poll cheaply for a pending check-in only while the user isn't already on
  // the workspace view (where the check-in card itself is the live source of
  // truth) — the nav badge and title marker exist precisely to be seen from
  // everywhere else.
  const pendingCheckIns = useCheckIns(projectId ?? "", "pending", {
    enabled: base !== null && !inWorkspace,
    refetchInterval: 15_000,
  });
  const hasPendingCheckIn = base !== null && !inWorkspace && (pendingCheckIns.data?.data.length ?? 0) > 0;

  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <TitleMarkerProvider active={hasPendingCheckIn}>
          <div className="min-h-svh">
            <NavBar>
              <div className="flex min-w-0 items-center gap-3">
                <NavItem to="/">
                  <NavLogo />
                </NavItem>
                {project.data !== undefined && (
                  <span className="flex min-w-0 items-center gap-2 text-meta text-grey">
                    <span aria-hidden="true" className="text-line-2">
                      /
                    </span>
                    <span className="truncate font-semibold text-navy">{scrub(project.data.name)}</span>
                  </span>
                )}
              </div>
              <div className="flex items-center gap-5">
                {base !== null && (
                  <>
                    <NavItem to={base}>
                      <span className="inline-flex items-center gap-1.5">
                        Workspace
                        {hasPendingCheckIn && (
                          <>
                            <StatusDot tone="paused" />
                            <span className="sr-only">Check-in pending</span>
                          </>
                        )}
                      </span>
                    </NavItem>
                    <NavItem to={`${base}/evidence-base`}>Evidence base</NavItem>
                    <NavItem to={`${base}/findings`}>Findings</NavItem>
                    <NavItem to={`${base}/sources`}>Sources</NavItem>
                    <NavItem to={`${base}/landscape`}>Landscape</NavItem>
                    <NavItem to={`${base}/decisions`}>Decision log</NavItem>
                  </>
                )}
                {/* 026 live-check gap: the AuthApi always had signOut; nothing
                    rendered it — Cognito users had no way out of a session. */}
                {auth.user !== null && (
                  <span className="flex items-center gap-3">
                    <span className="text-caption text-grey">{scrub(auth.user.sub)}</span>
                    <button
                      type="button"
                      onClick={() => auth.signOut()}
                      className="cursor-pointer text-meta text-grey hover:text-navy"
                    >
                      Sign out
                    </button>
                  </span>
                )}
              </div>
            </NavBar>
            <ErrorBoundary key={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </TitleMarkerProvider>
      </TooltipProvider>
    </ToastProvider>
  );
}
