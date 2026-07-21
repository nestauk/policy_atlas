import { Outlet, useParams } from "react-router";

import { useProject } from "../api/queries";
import { NavBar, NavItem, NavLogo } from "../ui/brand/Nav";
import { ToastProvider } from "../ui/radix/Toast";
import { TooltipProvider } from "../ui/radix/Tooltip";

/** App chrome: brand group left, project-scoped nav right (growing underline). */
export function AppShell() {
  const { projectId } = useParams();
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
                  <span className="truncate font-semibold text-navy">{project.data.name}</span>
                </span>
              )}
            </div>
            {base !== null && (
              <div className="flex items-center gap-5">
                <NavItem to={base}>Workspace</NavItem>
                <NavItem to={`${base}/evidence-base`}>Evidence base</NavItem>
                <NavItem to={`${base}/findings`}>Findings</NavItem>
                <NavItem to={`${base}/sources`}>Sources</NavItem>
                <NavItem to={`${base}/landscape`}>Landscape</NavItem>
                <NavItem to={`${base}/decisions`}>Decision log</NavItem>
              </div>
            )}
          </NavBar>
          <Outlet />
        </div>
      </TooltipProvider>
    </ToastProvider>
  );
}
