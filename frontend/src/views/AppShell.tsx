import { Outlet, useParams } from "react-router";

import { useProject } from "../api/queries";
import { useAuth } from "../auth";
import { scrub } from "../lib/scrub";
import { NavBar, NavItem, NavLogo } from "../ui/brand/Nav";
import { ToastProvider } from "../ui/radix/Toast";
import { TooltipProvider } from "../ui/radix/Tooltip";

/** App chrome: brand group left, project-scoped nav right (growing underline). */
export function AppShell() {
  const { projectId } = useParams();
  const auth = useAuth();
  const project = useProject(projectId ?? "");
  const base = projectId === undefined ? null : `/projects/${projectId}`;
  return (
    <ToastProvider>
      <TooltipProvider delayDuration={200}>
        <div className="min-h-svh">
          <NavBar>
            <div className="flex min-w-0 items-center gap-3">
              <NavItem to="/">
                <NavLogo />
              </NavItem>
              {project.data !== undefined && (
                <span className="flex min-w-0 items-center gap-2 text-[13px] text-grey">
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
                  <NavItem to={base}>Workspace</NavItem>
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
                <button
                  type="button"
                  onClick={() => auth.signOut()}
                  className="cursor-pointer text-[13px] text-grey hover:text-navy"
                >
                  Sign out
                </button>
              )}
            </div>
          </NavBar>
          <Outlet />
        </div>
      </TooltipProvider>
    </ToastProvider>
  );
}
